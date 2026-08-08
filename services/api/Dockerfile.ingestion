FROM public.ecr.aws/lambda/python:3.13@sha256:0f477aef4e304c869817ca6aeab02f71c900ea8de5e2e52f9a81b28371bad285

COPY requirements-ingestion.txt ${LAMBDA_TASK_ROOT}/requirements-ingestion.txt

RUN python -m pip install \
    --disable-pip-version-check \
    --no-cache-dir \
    --require-hashes \
    --requirement ${LAMBDA_TASK_ROOT}/requirements-ingestion.txt \
    --target ${LAMBDA_TASK_ROOT}

COPY src ${LAMBDA_TASK_ROOT}/src

CMD ["src.functions.ingestion.handler.lambda_handler"]
