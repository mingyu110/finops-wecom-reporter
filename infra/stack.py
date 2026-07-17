from aws_cdk import (
    Stack, Duration, RemovalPolicy,
    aws_s3 as s3,
    aws_sqs as sqs,
    aws_secretsmanager as secretsmanager,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_lambda_event_sources as event_sources,
    aws_scheduler as scheduler,
    aws_scheduler_targets as scheduler_targets,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    aws_sns as sns,
    TimeZone,
)
from constructs import Construct

AGENT_SPACE_ID = "1idud5y79e1zhhecnwl5klok"
FINOPS_REGION = "us-east-1"

# Lambda 打包项目根，使 `src` 作为包存在（源码用 from src.xxx 绝对导入）；
# 排除部署无关的大目录/杂物，避免把 .venv 等塞进 zip。
_CODE_EXCLUDE = [
    ".venv", ".git", "cdk.out", "tests", "docs", "infra", "scripts",
    ".superpowers", ".playwright-mcp", "*.md", "Makefile", "cdk.json",
    "requirements.txt", ".gitignore", "**/__pycache__", "**/*.pyc",
]


class FinOpsWeComStack(Stack):
    def __init__(self, scope: Construct, cid: str, **kwargs):
        super().__init__(scope, cid, **kwargs)

        # --- 产物中转桶（生命周期 7 天过期）---
        artifact_bucket = s3.Bucket(
            self, "ArtifactBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            lifecycle_rules=[s3.LifecycleRule(expiration=Duration.days(7))],
        )

        # --- SQS 主队列 + DLQ ---
        dlq = sqs.Queue(self, "ReportDLQ", retention_period=Duration.days(14))
        report_queue = sqs.Queue(
            self, "ReportQueue",
            visibility_timeout=Duration.seconds(300),
            dead_letter_queue=sqs.DeadLetterQueue(max_receive_count=3, queue=dlq),
        )

        # --- 企微 webhook key（占位，部署后手动填值）---
        wecom_secret = secretsmanager.Secret(
            self, "WeComWebhookSecret",
            description="WeCom group robot webhook key (fill via CLI after deploy)",
        )

        # --- Lambda① Orchestrator ---
        orchestrator = lambda_.Function(
            self, "Orchestrator",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="src.orchestrator.handler.lambda_handler",
            code=lambda_.Code.from_asset(".", exclude=_CODE_EXCLUDE),
            timeout=Duration.minutes(10),
            memory_size=256,
            environment={
                "AGENT_SPACE_ID": AGENT_SPACE_ID,
                "ARTIFACT_BUCKET": artifact_bucket.bucket_name,
                "REPORT_QUEUE_URL": report_queue.queue_url,
                "REPORT_PROMPT": "生成本月 AWS 成本概览报告，含 Top 服务、环比趋势与异常提示",
                "PERIOD": "monthly",
                "REGION": FINOPS_REGION,
            },
        )
        orchestrator.add_to_role_policy(iam.PolicyStatement(
            actions=[
                "finops-agent:CreateTask",
                "finops-agent:GetTask",
                "finops-agent:ListArtifacts",
                "finops-agent:GetArtifactContent",
            ],
            # FinOps Agent 不支持资源级 ARN，* 是唯一合法写法。见 Service Authorization Reference：
            # https://docs.aws.amazon.com/service-authorization/latest/reference/list_finops-agent.html
            resources=["*"],
        ))
        artifact_bucket.grant_put(orchestrator)
        report_queue.grant_send_messages(orchestrator)

        # --- Lambda② WeComAdapter ---
        adapter = lambda_.Function(
            self, "WeComAdapter",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="src.wecom_adapter.handler.lambda_handler",
            code=lambda_.Code.from_asset(".", exclude=_CODE_EXCLUDE),
            timeout=Duration.minutes(2),
            memory_size=256,
            environment={"WECOM_SECRET_ARN": wecom_secret.secret_arn},
        )
        adapter.add_event_source(event_sources.SqsEventSource(
            report_queue, batch_size=1,
        ))
        artifact_bucket.grant_read(adapter)
        wecom_secret.grant_read(adapter)

        # --- EventBridge Scheduler（tz Asia/Shanghai）---
        tz = TimeZone.of("Asia/Shanghai")
        target = scheduler_targets.LambdaInvoke(orchestrator)
        scheduler.Schedule(
            self, "DailySchedule",
            schedule=scheduler.ScheduleExpression.cron(
                minute="0", hour="9", day="*", month="*", time_zone=tz),
            target=target,
            description="Daily FinOps cost report at 09:00 CST",
        )
        scheduler.Schedule(
            self, "WeeklySchedule",
            schedule=scheduler.ScheduleExpression.cron(
                minute="0", hour="9", week_day="MON", time_zone=tz),
            target=target,
            description="Weekly FinOps cost report Mon 09:00 CST",
        )
        scheduler.Schedule(
            self, "MonthlySchedule",
            schedule=scheduler.ScheduleExpression.cron(
                minute="0", hour="9", day="1", month="*", time_zone=tz),
            target=target,
            description="Monthly FinOps cost report 1st 09:00 CST",
        )

        # --- DLQ 深度告警 ---
        alarm_topic = sns.Topic(self, "AlarmTopic")
        dlq.metric_approximate_number_of_messages_visible().create_alarm(
            self, "DLQNotEmptyAlarm",
            threshold=0,
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            alarm_description="Report DLQ has messages — WeCom push failing",
        ).add_alarm_action(cw_actions.SnsAction(alarm_topic))

        self.artifact_bucket = artifact_bucket
        self.report_queue = report_queue
        self.dlq = dlq
        self.wecom_secret = wecom_secret
