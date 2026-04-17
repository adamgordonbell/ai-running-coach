import json
import pulumi
import pulumi_aws as aws

config = pulumi.Config()
openai_key = config.require_secret("openaiApiKey")
slack_token = config.require_secret("slackBotToken")
slack_channel = config.require_secret("slackChannelId")
strava_client_id = config.require_secret("stravaClientId")
strava_client_secret = config.require_secret("stravaClientSecret")
strava_refresh_token = config.require_secret("stravaRefreshToken")
athlete_id = config.require("athleteId")

# Storage
activities_table = aws.dynamodb.Table(
    "activities",
    name="ai-running-coach-activities",
    billing_mode="PAY_PER_REQUEST",
    hash_key="athlete_id",
    range_key="start_date",
    attributes=[
        aws.dynamodb.TableAttributeArgs(name="athlete_id", type="S"),
        aws.dynamodb.TableAttributeArgs(name="start_date", type="S"),
    ],
)

context_bucket = aws.s3.Bucket("context", force_destroy=True)

# IAM
lambda_role = aws.iam.Role(
    "lambda-role",
    assume_role_policy=json.dumps({
        "Version": "2012-10-17",
        "Statement": [{"Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole"}],
    }),
)
aws.iam.RolePolicyAttachment("lambda-logs", role=lambda_role.name,
    policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole")
aws.iam.RolePolicy("lambda-data", role=lambda_role.id, policy=pulumi.Output.all(
    activities_table.arn, context_bucket.arn
).apply(lambda args: json.dumps({
    "Version": "2012-10-17",
    "Statement": [
        {"Effect": "Allow", "Action": ["dynamodb:PutItem", "dynamodb:Query"], "Resource": args[0]},
        {"Effect": "Allow", "Action": ["s3:GetObject", "s3:PutObject"], "Resource": f"{args[1]}/*"},
    ],
})))

# Lambda
fn = aws.lambda_.Function(
    "app",
    name="momentum-app",
    runtime="python3.12",
    code=pulumi.FileArchive("../app.zip"),
    handler="app.handler.lambda_handler",
    role=lambda_role.arn,
    timeout=900,
    memory_size=512,
    environment=aws.lambda_.FunctionEnvironmentArgs(variables=pulumi.Output.all(
        context_bucket.bucket, slack_token, slack_channel,
        strava_client_id, strava_client_secret, strava_refresh_token,
    ).apply(lambda v: {
        "CONTEXT_BUCKET": v[0], "ACTIVITIES_TABLE": "ai-running-coach-activities",
        "ATHLETE_ID": athlete_id, "OPENAI_API_KEY": openai_key,
        "SLACK_BOT_TOKEN": v[1], "SLACK_CHANNEL_ID": v[2],
        "STRAVA_CLIENT_ID": v[3], "STRAVA_CLIENT_SECRET": v[4],
        "STRAVA_REFRESH_TOKEN": v[5],
    })),
)

function_url = aws.lambda_.FunctionUrl("url",
    function_name=fn.name, authorization_type="NONE")

# EventBridge Scheduler — 6 AM ET daily
scheduler_role = aws.iam.Role(
    "scheduler-role",
    assume_role_policy=json.dumps({
        "Version": "2012-10-17",
        "Statement": [{"Effect": "Allow", "Principal": {"Service": "scheduler.amazonaws.com"}, "Action": "sts:AssumeRole"}],
    }),
)
aws.iam.RolePolicy("scheduler-invoke", role=scheduler_role.id,
    policy=fn.arn.apply(lambda arn: json.dumps({
        "Version": "2012-10-17",
        "Statement": [{"Effect": "Allow", "Action": "lambda:InvokeFunction", "Resource": arn}],
    })))

aws.scheduler.Schedule(
    "daily-checkin",
    schedule_expression="cron(0 6 * * ? *)",
    schedule_expression_timezone="America/New_York",
    flexible_time_window=aws.scheduler.ScheduleFlexibleTimeWindowArgs(mode="OFF"),
    target=aws.scheduler.ScheduleTargetArgs(
        arn=fn.arn,
        role_arn=scheduler_role.arn,
        input=json.dumps({"source": "aws.scheduler"}),
    ),
)

pulumi.export("function_url", function_url.function_url)
pulumi.export("context_bucket", context_bucket.bucket)
