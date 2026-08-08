FROM public.ecr.aws/lambda/python:3.13@sha256:0f477aef4e304c869817ca6aeab02f71c900ea8de5e2e52f9a81b28371bad285

COPY services/api/requirements-database-tools.txt ${LAMBDA_TASK_ROOT}/requirements-database-tools.txt

RUN python -m pip install \
    --disable-pip-version-check \
    --no-cache-dir \
    --require-hashes \
    --requirement ${LAMBDA_TASK_ROOT}/requirements-database-tools.txt \
    --target ${LAMBDA_TASK_ROOT}

COPY services/api/src/functions/database_migration ${LAMBDA_TASK_ROOT}/src/functions/database_migration
COPY packages/database/migrations ${LAMBDA_TASK_ROOT}/migrations

CMD ["src.functions.database_migration.handler.lambda_handler"]
