FROM public.ecr.aws/lambda/python:3.13@sha256:0f477aef4e304c869817ca6aeab02f71c900ea8de5e2e52f9a81b28371bad285

COPY services/api/requirements-database-tools.txt ${LAMBDA_TASK_ROOT}/requirements-database-tools.txt

RUN python -m pip install \
    --disable-pip-version-check \
    --no-cache-dir \
    --require-hashes \
    --requirement ${LAMBDA_TASK_ROOT}/requirements-database-tools.txt \
    --target ${LAMBDA_TASK_ROOT}

COPY services/api/src/functions/rds_connectivity ${LAMBDA_TASK_ROOT}/src/functions/rds_connectivity

CMD ["src.functions.rds_connectivity.handler.lambda_handler"]
