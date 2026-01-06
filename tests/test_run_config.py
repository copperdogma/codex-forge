import pytest
import yaml
from schemas import RunConfig

def test_run_config_minimal():
    data = {"recipe": "configs/recipes/smoke.yaml"}
    config = RunConfig(**data)
    assert config.recipe == "configs/recipes/smoke.yaml"
    assert config.registry == "modules"
    assert config.execution.skip_done is False

def test_run_config_full():
    yaml_data = """
run_id: my-run
recipe: configs/recipes/smoke.yaml
registry: custom_modules
execution:
  start_from: stage1
  force: true
options:
  mock: true
instrumentation:
  enabled: true
"""
    data = yaml.safe_load(yaml_data)
    config = RunConfig(**data)
    assert config.run_id == "my-run"
    assert config.execution.start_from == "stage1"
    assert config.execution.force is True
    assert config.options.mock is True
    assert config.instrumentation.enabled is True

def test_run_config_validation_error():
    # recipe is required
    with pytest.raises(ValueError):
        RunConfig()

def test_run_config_types():
    data = {
        "recipe": "some-recipe",
        "execution": {
            "skip_done": "not-a-bool"
        }
    }
    # Pydantic might try to coerce "not-a-bool" or fail
    with pytest.raises(ValueError):
        RunConfig(**data)
