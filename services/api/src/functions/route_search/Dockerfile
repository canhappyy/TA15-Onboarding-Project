FROM public.ecr.aws/lambda/python:3.13@sha256:0f477aef4e304c869817ca6aeab02f71c900ea8de5e2e52f9a81b28371bad285

COPY services/api/requirements-database-tools.txt ${LAMBDA_TASK_ROOT}/requirements-route-search.txt

RUN python -m pip install \
    --disable-pip-version-check \
    --no-cache-dir \
    --require-hashes \
    --requirement ${LAMBDA_TASK_ROOT}/requirements-route-search.txt \
    --target ${LAMBDA_TASK_ROOT}

COPY services/api/src/clients ${LAMBDA_TASK_ROOT}/src/clients
COPY services/api/src/common ${LAMBDA_TASK_ROOT}/src/common
COPY services/api/src/repositories ${LAMBDA_TASK_ROOT}/src/repositories
COPY services/api/src/scoring ${LAMBDA_TASK_ROOT}/src/scoring
COPY services/api/src/services ${LAMBDA_TASK_ROOT}/src/services
COPY services/api/src/functions/route_search ${LAMBDA_TASK_ROOT}/src/functions/route_search
COPY services/api/src/functions/location_search/assets ${LAMBDA_TASK_ROOT}/src/functions/location_search/assets

CMD ["src.functions.route_search.handler.lambda_handler"]
