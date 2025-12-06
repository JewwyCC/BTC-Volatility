#!/usr/bin/env python3
"""
Migrate MLflow runs from SQLite backend to file store format.

This script exports all runs from the SQLite database and recreates them
in the file store format where each run is stored as its own directory.
"""

import argparse
import logging
import os
import shutil
from pathlib import Path
from typing import Dict, List

import mlflow
from mlflow.tracking import MlflowClient
from mlflow.store.tracking.file_store import FileStore
import yaml

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def export_run_to_file_store(
    client: MlflowClient, run_id: str, experiment_id: str, file_store_path: str
) -> bool:
    """
    Export a single run from SQLite backend to file store format.

    Args:
        client: MLflow client connected to SQLite backend
        run_id: Run ID to export
        experiment_id: Experiment ID
        file_store_path: Path to file store root directory

    Returns:
        True if successful, False otherwise
    """
    try:
        # Get run details
        run = client.get_run(run_id)
        run_info = run.info

        # Create file store structure
        file_store = Path(file_store_path)
        experiment_dir = file_store / str(experiment_id)
        run_dir = experiment_dir / run_info.run_id

        # Create directories
        run_dir.mkdir(parents=True, exist_ok=True)

        # Write meta.yaml for the run
        meta = {
            "run_id": run_info.run_id,
            "experiment_id": str(experiment_id),
            "user_id": run_info.user_id or "",
            "status": run_info.status,
            "start_time": run_info.start_time,
            "end_time": run_info.end_time if run_info.end_time else None,
            "artifact_uri": run_info.artifact_uri,
            "lifecycle_stage": run_info.lifecycle_stage,
        }

        meta_path = run_dir / "meta.yaml"
        with open(meta_path, "w") as f:
            yaml.dump(meta, f, default_flow_style=False, sort_keys=False)

        # Write metrics
        metrics_dir = run_dir / "metrics"
        metrics_dir.mkdir(exist_ok=True)

        for metric in run.data.metrics:
            metric_file = metrics_dir / metric
            # Get metric history
            metric_history = client.get_metric_history(run_id, metric)
            if metric_history:
                # Write latest value (file store format uses single value per metric file)
                latest = metric_history[-1]
                with open(metric_file, "w") as f:
                    f.write(f"{latest.value}\n{latest.timestamp}\n{latest.step}\n")

        # Write parameters
        params_dir = run_dir / "params"
        params_dir.mkdir(exist_ok=True)

        for param_key, param_value in run.data.params.items():
            param_file = params_dir / param_key
            with open(param_file, "w") as f:
                f.write(str(param_value))

        # Write tags
        tags_dir = run_dir / "tags"
        tags_dir.mkdir(exist_ok=True)

        for tag_key, tag_value in run.data.tags.items():
            tag_file = tags_dir / tag_key
            with open(tag_file, "w") as f:
                f.write(str(tag_value))

        logger.info(f"✓ Exported run {run_info.run_id} ({run_info.run_name})")
        return True

    except Exception as e:
        logger.error(f"✗ Failed to export run {run_id}: {e}")
        return False


def migrate_experiment(
    client: MlflowClient, experiment_name: str, file_store_path: str
) -> int:
    """
    Migrate all runs from an experiment to file store format.

    Args:
        client: MLflow client connected to SQLite backend
        experiment_name: Name of experiment to migrate
        file_store_path: Path to file store root directory

    Returns:
        Number of runs successfully migrated
    """
    try:
        # Get experiment
        experiment = client.get_experiment_by_name(experiment_name)
        if experiment is None:
            logger.error(f"Experiment '{experiment_name}' not found")
            return 0

        logger.info(
            f"Found experiment '{experiment_name}' (ID: {experiment.experiment_id})"
        )

        # Create experiment directory and meta.yaml
        file_store = Path(file_store_path)
        experiment_dir = file_store / str(experiment.experiment_id)
        experiment_dir.mkdir(parents=True, exist_ok=True)

        # Write experiment meta.yaml
        exp_meta = {
            "experiment_id": str(experiment.experiment_id),
            "name": experiment.name,
            "artifact_location": experiment.artifact_location,
            "lifecycle_stage": experiment.lifecycle_stage,
            "tags": (
                {k: v for k, v in experiment.tags.items()}
                if hasattr(experiment, "tags")
                else {}
            ),
        }

        exp_meta_path = experiment_dir / "meta.yaml"
        with open(exp_meta_path, "w") as f:
            yaml.dump(exp_meta, f, default_flow_style=False, sort_keys=False)

        # Get all runs
        runs = client.search_runs(experiment_ids=[experiment.experiment_id])
        logger.info(f"Found {len(runs)} runs to migrate")

        # Export each run
        success_count = 0
        for run in runs:
            if export_run_to_file_store(
                client, run.info.run_id, experiment.experiment_id, file_store_path
            ):
                success_count += 1

        logger.info(f"Successfully migrated {success_count}/{len(runs)} runs")
        return success_count

    except Exception as e:
        logger.error(f"Failed to migrate experiment: {e}")
        return 0


def main():
    parser = argparse.ArgumentParser(
        description="Migrate MLflow runs from SQLite to file store"
    )
    parser.add_argument(
        "--mlflow_uri",
        type=str,
        default="http://localhost:5001",
        help="MLflow tracking URI (SQLite backend)",
    )
    parser.add_argument(
        "--experiment_name",
        type=str,
        default="volatility_detection",
        help="Experiment name to migrate",
    )
    parser.add_argument(
        "--file_store_path",
        type=str,
        default="/mlflow/mlruns",
        help="Path to file store root directory",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Backup existing file store before migration",
    )

    args = parser.parse_args()

    # Connect to SQLite backend
    logger.info(f"Connecting to MLflow at {args.mlflow_uri}...")
    mlflow.set_tracking_uri(args.mlflow_uri)
    client = MlflowClient(args.mlflow_uri)

    # Backup if requested
    file_store_path = Path(args.file_store_path)
    if args.backup and file_store_path.exists():
        backup_path = file_store_path.parent / f"{file_store_path.name}.backup"
        logger.info(f"Backing up existing file store to {backup_path}...")
        if backup_path.exists():
            shutil.rmtree(backup_path)
        shutil.copytree(file_store_path, backup_path)
        logger.info("✓ Backup created")

    # Create file store directory
    file_store_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"File store path: {file_store_path}")

    # Migrate experiment
    success_count = migrate_experiment(
        client, args.experiment_name, str(file_store_path)
    )

    if success_count > 0:
        logger.info(
            f"\n✓ Migration complete! {success_count} runs migrated to file store."
        )
        logger.info(f"File store location: {file_store_path}")
    else:
        logger.error("Migration failed or no runs were migrated")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
