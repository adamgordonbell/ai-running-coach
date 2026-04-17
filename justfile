function_url := `pulumi -C infra stack output function_url 2>/dev/null || echo "not deployed"`

# Package app code + prompts + dependencies into a zip for Lambda
package:
    #!/usr/bin/env bash
    rm -rf /tmp/lambda-pkg && mkdir /tmp/lambda-pkg
    uv pip install openai boto3 httpx --target /tmp/lambda-pkg --python-platform x86_64-manylinux_2_28 --python-version 3.12 --quiet
    cp -r app prompts /tmp/lambda-pkg/
    cd /tmp/lambda-pkg && zip -r {{justfile_directory()}}/app.zip . -x "**/__pycache__/*" "**/*.pyc" "**/*.dist-info/*" > /dev/null
    echo "app.zip built: $(du -sh {{justfile_directory()}}/app.zip | cut -f1)"

# Deploy to AWS
deploy: package
    cd infra && pulumi up

# Tear down all AWS resources
destroy:
    cd infra && pulumi destroy

# Seed athlete_context.md to S3 (run once after deploy)
seed:
    #!/usr/bin/env bash
    bucket=$(cd infra && pulumi stack output context_bucket)
    aws s3 cp prompts/athlete_context.md s3://$bucket/athlete_context.md

# Trigger the 6am morning check-in path
invoke-cron:
    aws lambda invoke \
        --function-name momentum-app \
        --payload '{"source":"aws.scheduler"}' \
        --cli-binary-format raw-in-base64-out \
        /tmp/cron-out.json && cat /tmp/cron-out.json

# POST a canned Strava webhook payload to the FunctionURL
invoke-webhook:
    curl -s -X POST {{function_url}} \
        -H "Content-Type: application/json" \
        -d @test-fixtures/strava-webhook.json | jq .

# Tail Lambda logs
tail-logs:
    aws logs tail /aws/lambda/momentum-app --follow
