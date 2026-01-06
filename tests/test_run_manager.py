import os
import shutil
import subprocess
import pytest
import yaml

RUN_MANAGER = "tools/run_manager.py"
RUNS_DIR = "runs"

@pytest.fixture
def cleanup_runs():
    if os.path.exists(RUNS_DIR):
        shutil.rmtree(RUNS_DIR)
    yield
    if os.path.exists(RUNS_DIR):
        shutil.rmtree(RUNS_DIR)

def test_create_run(cleanup_runs):
    run_name = "integration-test-run"
    subprocess.run(["python", RUN_MANAGER, "create-run", run_name], check=True)
    
    expected_path = os.path.join(RUNS_DIR, f"{run_name}.yaml")
    assert os.path.exists(expected_path)
    
    with open(expected_path, "r") as f:
        content = f.read()
        assert "recipe: configs/recipes/recipe-ff-smoke.yaml" in content
        assert f"run_id: {run_name}" in content

def test_execute_run_dry_run(cleanup_runs):
    run_name = "exec-test"
    
    # Create a dummy recipe so driver.py can load it
    dummy_recipe = "configs/recipes/dummy.yaml"
    os.makedirs(os.path.dirname(dummy_recipe), exist_ok=True)
    with open(dummy_recipe, "w") as f:
        f.write("name: dummy-recipe\n")
    
    subprocess.run(["python", RUN_MANAGER, "create-run", run_name], check=True)
    
    # Update the created run config to point to our dummy recipe
    expected_path = os.path.join(RUNS_DIR, f"{run_name}.yaml")
    with open(expected_path, "r") as f:
        config_data = yaml.safe_load(f)
    config_data["recipe"] = dummy_recipe
    with open(expected_path, "w") as f:
        yaml.dump(config_data, f)

    # We use --dry-run so driver.py doesn't actually do anything 
    # and we can check if it invoked correctly.
    result = subprocess.run(
        ["python", RUN_MANAGER, "execute-run", run_name, "--dry-run"],
        capture_output=True,
        text=True
    )
    
    # Check if driver.py was called and recognized the config
    assert "Executing:" in result.stdout
    assert "driver.py --config" in result.stdout
    assert f"runs/{run_name}.yaml" in result.stdout
    assert "--dry-run" in result.stdout

    # Cleanup dummy recipe
    if os.path.exists(dummy_recipe):
        os.remove(dummy_recipe)
