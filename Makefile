.PHONY: test deploy demo destroy

# 跑全量单测（使用 venv 的 pytest）
test:
	.venv/bin/python -m pytest tests/ -v

# 部署（依赖修正后的 cdk.json：.venv/bin/python -m infra.app）
deploy:
	cdk deploy --require-approval never

# 手动触发一次 Orchestrator（模拟 Scheduler），验证端到端推送
demo:
	aws lambda invoke --function-name $$(aws cloudformation describe-stack-resource \
	  --stack-name FinOpsWeComStack --logical-resource-id Orchestrator \
	  --query 'StackResourceDetail.PhysicalResourceId' --output text) \
	  --payload '{"date":"manual-demo"}' --cli-binary-format raw-in-base64-out /dev/stdout

# 销毁整个 stack
destroy:
	cdk destroy --force
