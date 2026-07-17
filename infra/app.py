import os
import aws_cdk as cdk
from infra.stack import FinOpsWeComStack

app = cdk.App()
# 账号/区域由环境变量注入，避免把具体账号写死在仓库里。
# CDK_DEFAULT_ACCOUNT / CDK_DEFAULT_REGION 会由 CDK CLI 从当前 AWS 凭证自动填充；
# 也可显式 export 覆盖。FinOps Agent 预览期仅支持 us-east-1，故 region 缺省回退到该值。
FinOpsWeComStack(
    app, "FinOpsWeComStack",
    env=cdk.Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region=os.environ.get("CDK_DEFAULT_REGION", "us-east-1"),
    ),
)
app.synth()
