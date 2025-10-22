"""
DAG 테스트 스크립트
pytest를 사용하여 Airflow DAG을 검증합니다.

실행 방법:
    pytest tests/test_dag.py -v
"""

import pytest
from datetime import datetime, timedelta
from airflow.models import DagBag
from airflow.utils.dag_cycle_tester import check_cycle
import sys
import os

# DAG 경로 추가
DAG_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'airflow', 'dags')


class TestDAGIntegrity:
    """DAG 구조 및 무결성 테스트"""

    @pytest.fixture(scope="class")
    def dagbag(self):
        """DagBag 픽스처 - 모든 DAG을 로드"""
        return DagBag(dag_folder=DAG_FOLDER, include_examples=False)

    def test_dagbag_import(self, dagbag):
        """DAG 파일 import 오류 체크"""
        assert len(dagbag.import_errors) == 0, \
            f"DAG import 오류: {dagbag.import_errors}"

    def test_dag_loaded(self, dagbag):
        """DAG이 정상적으로 로드되었는지 확인"""
        dag_id = 'neologism_extraction_pipeline'
        assert dag_id in dagbag.dags, f"DAG '{dag_id}'를 찾을 수 없습니다."
        assert dagbag.dags[dag_id] is not None

    def test_dag_has_tags(self, dagbag):
        """DAG에 태그가 설정되어 있는지 확인"""
        dag_id = 'neologism_extraction_pipeline'
        dag = dagbag.dags[dag_id]
        assert len(dag.tags) > 0, "DAG에 태그가 없습니다."
        assert 'nlp' in dag.tags
        assert 'neologism' in dag.tags

    def test_dag_cycle(self, dagbag):
        """DAG에 순환 의존성이 없는지 확인"""
        dag_id = 'neologism_extraction_pipeline'
        dag = dagbag.dags[dag_id]
        check_cycle(dag)  # 순환이 있으면 예외 발생

    def test_dag_schedule(self, dagbag):
        """DAG 스케줄이 올바르게 설정되어 있는지 확인"""
        dag_id = 'neologism_extraction_pipeline'
        dag = dagbag.dags[dag_id]
        assert dag.schedule_interval == '0 2 * * *', \
            f"잘못된 스케줄: {dag.schedule_interval}"

    def test_dag_default_args(self, dagbag):
        """DAG default_args 검증"""
        dag_id = 'neologism_extraction_pipeline'
        dag = dagbag.dags[dag_id]
        assert dag.default_args['owner'] == 'data-team'
        assert dag.default_args['retries'] == 2
        assert dag.default_args['retry_delay'] == timedelta(minutes=5)


class TestDAGTasks:
    """DAG Task 테스트"""

    @pytest.fixture(scope="class")
    def dag(self):
        """DAG 픽스처"""
        dagbag = DagBag(dag_folder=DAG_FOLDER, include_examples=False)
        return dagbag.dags['neologism_extraction_pipeline']

    def test_task_count(self, dag):
        """Task 개수 확인"""
        # start, collect_twitter, collect_aihub, data_collection_complete,
        # run_glue_job, wait_for_glue, validate, notify, end
        assert len(dag.tasks) == 9, f"예상 Task 수: 9, 실제: {len(dag.tasks)}"

    def test_required_tasks_exist(self, dag):
        """필수 Task가 존재하는지 확인"""
        required_tasks = [
            'start',
            'collect_twitter_data',
            'collect_aihub_data',
            'data_collection_complete',
            'run_neologism_extraction_glue_job',
            'wait_for_glue_job',
            'validate_results',
            'send_notification',
            'end',
        ]
        task_ids = [task.task_id for task in dag.tasks]
        for task_id in required_tasks:
            assert task_id in task_ids, f"Task '{task_id}'를 찾을 수 없습니다."

    def test_task_dependencies(self, dag):
        """Task 의존성 확인"""
        # start → [collect_twitter, collect_aihub]
        start_task = dag.get_task('start')
        downstream_task_ids = [t.task_id for t in start_task.downstream_list]
        assert 'collect_twitter_data' in downstream_task_ids
        assert 'collect_aihub_data' in downstream_task_ids

        # data_collection_complete → run_glue_job
        collect_complete = dag.get_task('data_collection_complete')
        assert 'run_neologism_extraction_glue_job' in \
               [t.task_id for t in collect_complete.downstream_list]

        # validate → notify
        validate_task = dag.get_task('validate_results')
        assert 'send_notification' in \
               [t.task_id for t in validate_task.downstream_list]

    def test_glue_job_operator_config(self, dag):
        """GlueJobOperator 설정 확인"""
        glue_task = dag.get_task('run_neologism_extraction_glue_job')
        assert glue_task.job_name is not None
        assert glue_task.script_args is not None

        # 중요한 파라미터 확인
        script_args = glue_task.script_args
        assert '--INPUT_BUCKET' in script_args
        assert '--OUTPUT_BUCKET' in script_args
        assert '--ENABLE_DEDUP' in script_args
        assert script_args['--ENABLE_DEDUP'] == 'true'
        assert '--UPDATE_STRATEGY' in script_args

    def test_task_retries(self, dag):
        """Task별 retry 설정 확인"""
        for task in dag.tasks:
            # 모든 task는 최소 1번 이상 재시도
            retries = task.retries if task.retries is not None else dag.default_args.get('retries', 0)
            assert retries >= 1, f"Task '{task.task_id}'의 retries가 부족: {retries}"

    def test_task_timeout(self, dag):
        """Task 타임아웃 설정 확인"""
        # 전체 DAG 타임아웃
        assert dag.default_args.get('execution_timeout') is not None


class TestDAGExecution:
    """DAG 실행 테스트 (모의 실행)"""

    @pytest.fixture(scope="class")
    def dag(self):
        """DAG 픽스처"""
        dagbag = DagBag(dag_folder=DAG_FOLDER, include_examples=False)
        return dagbag.dags['neologism_extraction_pipeline']

    def test_dag_is_valid(self, dag):
        """DAG이 유효한지 확인"""
        from airflow.models import DagBag
        # DAG 유효성 검사
        assert dag is not None
        assert dag.dag_id == 'neologism_extraction_pipeline'

    def test_no_import_errors(self):
        """import 오류가 없는지 확인"""
        dagbag = DagBag(dag_folder=DAG_FOLDER, include_examples=False)
        assert len(dagbag.import_errors) == 0

    def test_catchup_disabled(self, dag):
        """catchup이 비활성화되어 있는지 확인 (과거 실행 방지)"""
        assert dag.catchup is False

    def test_max_active_runs(self, dag):
        """동시 실행 제한 확인"""
        assert dag.max_active_runs == 1


class TestPythonCallables:
    """Python 함수 테스트"""

    def test_imports(self):
        """DAG 파일의 모든 import가 성공하는지 확인"""
        try:
            sys.path.insert(0, DAG_FOLDER)
            import neologism_extraction_dag
            assert neologism_extraction_dag is not None
        except ImportError as e:
            pytest.fail(f"Import 실패: {e}")

    def test_functions_exist(self):
        """필요한 함수들이 존재하는지 확인"""
        sys.path.insert(0, DAG_FOLDER)
        import neologism_extraction_dag

        assert hasattr(neologism_extraction_dag, 'collect_twitter_data')
        assert hasattr(neologism_extraction_dag, 'collect_aihub_data')
        assert hasattr(neologism_extraction_dag, 'validate_results')
        assert hasattr(neologism_extraction_dag, 'send_notification')


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
