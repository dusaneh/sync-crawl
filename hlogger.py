import datetime
import time
import json
import os
from pathlib import Path
import datetime
import time
import json
import os
from pathlib import Path
import helper as hlp

class FolderExistsError(Exception):
    """Raised when attempting to create a folder that already exists."""
    pass

class LogOverwriteError(Exception):
    """Raised when attempting to overwrite an existing key (other than 'open_log')."""
    pass

class HierarchicalLogger:
    def __init__(self, client_folder=None):
        """
        Initialize the logger with an optional JSON file path and base folder path.
        If the file exists, load the data from it.
        """
        self.client_folder = client_folder
        self.json_file_path = Path(client_folder+'/logger.json')
        self.base_folder_path = Path("./")
        
        # Try to load existing data from JSON file
        if self.json_file_path.exists():
            try:
                hlp.ensure_writable_file_path(self.json_file_path)
                with open(self.json_file_path, 'r') as f:
                    self.data = json.load(f)
                    # Convert ISO format strings back to datetime objects
                    self._convert_datetime_strings_to_objects(self.data)
            except json.JSONDecodeError:
                # If file is corrupt or empty, start fresh
                self.data = {"workflows": {}}

            except (PermissionError, FileNotFoundError, NotADirectoryError) as e:
                print(f"Cannot write to file path: {self.json_file_path} -> {e}")
                raise  # 🔥 re-raise to stop execution

        else:
            self.data = {"workflows": {}}

        # The "context" dictionary holds the current path (IDs)
        self.context = {
            "workflow_id": None,
            "sample_id": None,
            "rerun_id": None,
            "run_id": None,
            "run_retry_id": None,
            "action_id": None,
            "candidate_id": None
        }

        # Define the hierarchy of context keys for cascade clearing
        self.context_hierarchy = [
            "workflow_id",
            "sample_id",
            "rerun_id",
            "run_id",
            "run_retry_id",
            "action_id",
            "candidate_id"
        ]

    def _get_folder_path(self, workflow_id=None, sample_id=None, rerun_id=None, 
                        run_id=None, run_retry_id=None):
        """
        Build the folder path based on provided IDs.
        Returns a Path object for the constructed path.
        """
        parts = [self.client_folder]
        if workflow_id is not None:
            parts.append(str(workflow_id))
            if sample_id is not None:
                parts.append(str(sample_id))
                if rerun_id is not None:
                    parts.append(str(rerun_id))
                    if run_id is not None:
                        parts.append(str(run_id))
                        if run_retry_id is not None:
                            parts.append(str(run_retry_id))
        
        return self.base_folder_path.joinpath(*parts) if parts else self.base_folder_path

    def _create_leaf_folders(self, folder_path):
        """Create the standard subdirectories in leaf folders."""
        for subdir in ['dots', 'temp', 'highlights','chunks']:
            subdir_path = folder_path / subdir
            subdir_path.mkdir(exist_ok=True,mode=0o755)

    def _create_folder_structure(self, workflow_id=None, sample_id=None, rerun_id=None,
                               run_id=None, run_retry_id=None, check_exists=True):
        """
        Create the folder structure for the given hierarchy level.
        If check_exists is True, raise FolderExistsError if the target folder exists.
        """
        folder_path = self._get_folder_path(
            workflow_id, sample_id, rerun_id, run_id, run_retry_id
        )
        
        if check_exists and folder_path.exists():
            raise FolderExistsError(f"Folder already exists: {folder_path}")

        folder_path.mkdir(parents=True, exist_ok=not check_exists,mode=0o755)
        
        # If this is a leaf node (run_retry level), create standard subdirectories
        if run_retry_id is not None:
            self._create_leaf_folders(folder_path)

        return folder_path

    def _init_folder_structure(self):
        """Initialize the folder structure based on current context."""
        if self.context["workflow_id"] is not None:
            self._create_folder_structure(
                workflow_id=self.context["workflow_id"],
                check_exists=False
            )
            
            if self.context["sample_id"] is not None:
                self._create_folder_structure(
                    workflow_id=self.context["workflow_id"],
                    sample_id=self.context["sample_id"],
                    check_exists=False
                )
                
                if self.context["rerun_id"] is not None:
                    self._create_folder_structure(
                        workflow_id=self.context["workflow_id"],
                        sample_id=self.context["sample_id"],
                        rerun_id=self.context["rerun_id"],
                        check_exists=False
                    )
                    
                    if self.context["run_id"] is not None:
                        self._create_folder_structure(
                            workflow_id=self.context["workflow_id"],
                            sample_id=self.context["sample_id"],
                            rerun_id=self.context["rerun_id"],
                            run_id=self.context["run_id"],
                            check_exists=False
                        )
                        
                        if self.context["run_retry_id"] is not None:
                            self._create_folder_structure(
                                workflow_id=self.context["workflow_id"],
                                sample_id=self.context["sample_id"],
                                rerun_id=self.context["rerun_id"],
                                run_id=self.context["run_id"],
                                run_retry_id=self.context["run_retry_id"],
                                check_exists=False
                            )


    def _clear_context_below(self, level: str):
        """
        Clear all context values below the specified level in the hierarchy.
        
        Args:
            level (str): The context level from which to clear all lower levels
        """
        if level not in self.context_hierarchy:
            raise ValueError(f"Invalid context level: {level}")
            
        level_index = self.context_hierarchy.index(level)
        for key in self.context_hierarchy[level_index + 1:]:
            self.context[key] = None

    def _convert_datetime_strings_to_objects(self, data_dict):
        """Recursively convert ISO format datetime strings to datetime objects."""
        if isinstance(data_dict, dict):
            if "created_at" in data_dict:
                data_dict["created_at"] = datetime.datetime.fromisoformat(data_dict["created_at"])
            for value in data_dict.values():
                self._convert_datetime_strings_to_objects(value)
        elif isinstance(data_dict, list):
            for item in data_dict:
                self._convert_datetime_strings_to_objects(item)

    def _convert_datetime_objects_to_strings(self, data_dict):
        """Create a copy of the data with datetime objects converted to ISO format strings."""
        if isinstance(data_dict, dict):
            result = {}
            for key, value in data_dict.items():
                if isinstance(value, datetime.datetime):
                    result[key] = value.isoformat()
                else:
                    result[key] = self._convert_datetime_objects_to_strings(value)
            return result
        elif isinstance(data_dict, list):
            return [self._convert_datetime_objects_to_strings(item) for item in data_dict]
        else:
            return data_dict


    def _save_to_json(self):
        self.json_file_path.parent.mkdir(parents=True, exist_ok=True,mode=0o755)
        json_safe_data = self._convert_datetime_objects_to_strings(self.data)
        
        # Write to a temp file first
        temp_path = self.json_file_path.with_suffix('.tmp')
        with open(temp_path, 'w') as f:
            json.dump(json_safe_data, f, indent=2)

        # Retry the final "replace" a few times if Windows is locking the file
        for attempt in range(5):
            try:
                temp_path.replace(self.json_file_path)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.2)

    def _create_node(self, parent_dict, node_id):
        """Create a new node if it doesn't exist."""
        if node_id not in parent_dict:
            parent_dict[node_id] = {
                "created_at": datetime.datetime.utcnow(),
                "open_log": []
            }
            self._save_to_json()
        return parent_dict[node_id]

    def _set_key_value(self, node: dict, key: str, value):
        """Set a key-value pair in the node."""
        if key == "open_log":
            node["open_log"].append(value)
        else:
            if key in node and key not in ["created_at", "open_log"]:
                raise LogOverwriteError(f"Key '{key}' already exists in this node; cannot overwrite.")
            node[key] = value
        
        self._save_to_json()

    def _create_node_if_needed(self,
                             workflow_id,
                             sample_id=None,
                             rerun_id=None,
                             run_id=None,
                             run_retry_id=None,
                             action_id=None,
                             candidate_id=None):
        """Traverse or create all necessary dictionaries down to the specified node."""
        # 1) Workflow
        wf_dict = self.data["workflows"]
        workflow_node = self._create_node(wf_dict, workflow_id)

        # 2) Sample
        if sample_id is not None:
            if "samples" not in workflow_node:
                workflow_node["samples"] = {}
            sample_node = self._create_node(workflow_node["samples"], sample_id)
        else:
            return workflow_node

        # 3) Rerun
        if rerun_id is not None:
            if "reruns" not in sample_node:
                sample_node["reruns"] = {}
            rerun_node = self._create_node(sample_node["reruns"], rerun_id)
        else:
            return sample_node

        # 4) Run
        if run_id is not None:
            if "runs" not in rerun_node:
                rerun_node["runs"] = {}
            run_node = self._create_node(rerun_node["runs"], run_id)
        else:
            return rerun_node

        # 5) Run Retry
        if run_retry_id is not None:
            if "run_retries" not in run_node:
                run_node["run_retries"] = {}
            run_retry_node = self._create_node(run_node["run_retries"], run_retry_id)
        else:
            return run_node

        # 6) Action
        if action_id is not None:
            if "actions" not in run_retry_node:
                run_retry_node["actions"] = {}
            action_node = self._create_node(run_retry_node["actions"], action_id)
        else:
            return run_retry_node

        # 7) Candidate
        if candidate_id is not None:
            if "candidates" not in action_node:
                action_node["candidates"] = {}
            candidate_node = self._create_node(action_node["candidates"], candidate_id)
            return candidate_node
        else:
            return action_node


    # Modify the set_* methods to create folders
    def set_workflow(self, workflow_id: str):
        """Update context with a workflow_id and clear all lower contexts."""
        folder_path = self._create_folder_structure(workflow_id=workflow_id)
        self.context["workflow_id"] = workflow_id
        self._clear_context_below("workflow_id")
        self._create_node_if_needed(workflow_id)


    def set_sample(self, sample_id: int = None) -> int:
        """
        Update context with a sample_id and clear all lower contexts.
        If sample_id is not provided, automatically generates the next available ID.
        
        Args:
            sample_id (int, optional): Specific sample ID to set. If None, auto-generates next ID.
            
        Returns:
            int: The sample ID that was set (either provided or auto-generated)
        
        Raises:
            ValueError: If workflow is not set or if provided sample_id already exists
        """
        if self.context["workflow_id"] is None:
            raise ValueError("Must set workflow before setting sample.")
            
        # If no sample_id provided, generate the next available one
        if sample_id is None:
            workflow_node = self.data["workflows"][self.context["workflow_id"]]
            existing_samples = set()
            
            # Get existing sample IDs
            if "samples" in workflow_node:
                existing_samples = {int(sid) for sid in workflow_node["samples"].keys()}
            
            # Find the next available ID (start from 0)
            sample_id = 0
            while sample_id in existing_samples:
                sample_id += 1

        # Create the folder structure (this will raise FolderExistsError if exists)
        folder_path = self._create_folder_structure(
            workflow_id=self.context["workflow_id"],
            sample_id=sample_id
        )
        
        self.context["sample_id"] = sample_id
        self._clear_context_below("sample_id")
        self._create_node_if_needed(
            workflow_id=self.context["workflow_id"],
            sample_id=sample_id
        )
        
        return sample_id

    def set_rerun(self, rerun_id: int):
        """Update context with a rerun_id and clear all lower contexts."""
        required = ["workflow_id", "sample_id"]
        for r in required:
            if self.context[r] is None:
                raise ValueError(f"Context '{r}' must be set before rerun.")
        folder_path = self._create_folder_structure(
            workflow_id=self.context["workflow_id"],
            sample_id=self.context["sample_id"],
            rerun_id=rerun_id
        )
        self.context["rerun_id"] = rerun_id
        self._clear_context_below("rerun_id")
        self._create_node_if_needed(
            workflow_id=self.context["workflow_id"],
            sample_id=self.context["sample_id"],
            rerun_id=rerun_id
        )

    def set_run(self, run_id: int):
        """Update context with a run_id and clear all lower contexts."""
        required = ["workflow_id", "sample_id", "rerun_id"]
        for r in required:
            if self.context[r] is None:
                raise ValueError(f"Context '{r}' must be set before run.")
        folder_path = self._create_folder_structure(
            workflow_id=self.context["workflow_id"],
            sample_id=self.context["sample_id"],
            rerun_id=self.context["rerun_id"],
            run_id=run_id
        )
        self.context["run_id"] = run_id
        self._clear_context_below("run_id")
        self._create_node_if_needed(
            workflow_id=self.context["workflow_id"],
            sample_id=self.context["sample_id"],
            rerun_id=self.context["rerun_id"],
            run_id=run_id
        )

    def set_run_retry(self, run_retry_id: int):
        """Update context with a run_retry_id and clear all lower contexts."""
        required = ["workflow_id", "sample_id", "rerun_id", "run_id"]
        for r in required:
            if self.context[r] is None:
                raise ValueError(f"Context '{r}' must be set before run_retry.")
        folder_path = self._create_folder_structure(
            workflow_id=self.context["workflow_id"],
            sample_id=self.context["sample_id"],
            rerun_id=self.context["rerun_id"],
            run_id=self.context["run_id"],
            run_retry_id=run_retry_id
        )
        self.context["run_retry_id"] = run_retry_id
        self._clear_context_below("run_retry_id")
        self._create_node_if_needed(
            workflow_id=self.context["workflow_id"],
            sample_id=self.context["sample_id"],
            rerun_id=self.context["rerun_id"],
            run_id=self.context["run_id"],
            run_retry_id=run_retry_id
        )
    def set_action(self, action_id: int):
        """Update context with an action_id and clear all lower contexts."""
        required = ["workflow_id", "sample_id", "rerun_id", "run_id", "run_retry_id"]
        for r in required:
            if self.context[r] is None:
                raise ValueError(f"Context '{r}' must be set before action.")
        self.context["action_id"] = action_id
        self._clear_context_below("action_id")
        self._create_node_if_needed(
            workflow_id=self.context["workflow_id"],
            sample_id=self.context["sample_id"],
            rerun_id=self.context["rerun_id"],
            run_id=self.context["run_id"],
            run_retry_id=self.context["run_retry_id"],
            action_id=action_id
        )

    def set_candidate(self, candidate_id: int):
        """Update context with a candidate_id."""
        required = ["workflow_id", "sample_id", "rerun_id", "run_id", "run_retry_id", "action_id"]
        for r in required:
            if self.context[r] is None:
                raise ValueError(f"Context '{r}' must be set before candidate.")
        self.context["candidate_id"] = candidate_id
        self._create_node_if_needed(
            workflow_id=self.context["workflow_id"],
            sample_id=self.context["sample_id"],
            rerun_id=self.context["rerun_id"],
            run_id=self.context["run_id"],
            run_retry_id=self.context["run_retry_id"],
            action_id=self.context["action_id"],
            candidate_id=candidate_id
        )
    # The rest of the methods (set_*_value and append_to_open_log_*) remain unchanged
    # as they rely on the context which is now properly managed by the setters above

    # ---------------------------------------------------------------------
    # "Set Value" Methods (No IDs, everything comes from self.context)
    # ---------------------------------------------------------------------
    def set_workflow_value(self, key: str, value):
        if self.context["workflow_id"] is None:
            raise ValueError("workflow_id must be set in context before setting workflow value.")
        node = self._create_node_if_needed(
            workflow_id=self.context["workflow_id"]
        )
        self._set_key_value(node, key, value)

    def set_sample_value(self, key: str, value):
        required = ["workflow_id", "sample_id"]
        for r in required:
            if self.context[r] is None:
                raise ValueError(f"Context '{r}' must be set before setting sample value.")
        node = self._create_node_if_needed(
            workflow_id=self.context["workflow_id"],
            sample_id=self.context["sample_id"]
        )
        self._set_key_value(node, key, value)

    def set_rerun_value(self, key: str, value):
        required = ["workflow_id", "sample_id", "rerun_id"]
        for r in required:
            if self.context[r] is None:
                raise ValueError(f"Context '{r}' must be set before setting rerun value.")
        node = self._create_node_if_needed(
            workflow_id=self.context["workflow_id"],
            sample_id=self.context["sample_id"],
            rerun_id=self.context["rerun_id"]
        )
        self._set_key_value(node, key, value)

    def set_run_value(self, key: str, value):
        required = ["workflow_id", "sample_id", "rerun_id", "run_id"]
        for r in required:
            if self.context[r] is None:
                raise ValueError(f"Context '{r}' must be set before setting run value.")
        node = self._create_node_if_needed(
            workflow_id=self.context["workflow_id"],
            sample_id=self.context["sample_id"],
            rerun_id=self.context["rerun_id"],
            run_id=self.context["run_id"]
        )
        self._set_key_value(node, key, value)

    def set_run_retry_value(self, key: str, value):
        required = ["workflow_id", "sample_id", "rerun_id", "run_id", "run_retry_id"]
        for r in required:
            if self.context[r] is None:
                raise ValueError(f"Context '{r}' must be set before setting run_retry value.")
        node = self._create_node_if_needed(
            workflow_id=self.context["workflow_id"],
            sample_id=self.context["sample_id"],
            rerun_id=self.context["rerun_id"],
            run_id=self.context["run_id"],
            run_retry_id=self.context["run_retry_id"]
        )
        self._set_key_value(node, key, value)

    def set_action_value(self, key: str, value):
        required = ["workflow_id", "sample_id", "rerun_id", "run_id", "run_retry_id", "action_id"]
        for r in required:
            if self.context[r] is None:
                raise ValueError(f"Context '{r}' must be set before setting action value.")
        node = self._create_node_if_needed(
            workflow_id=self.context["workflow_id"],
            sample_id=self.context["sample_id"],
            rerun_id=self.context["rerun_id"],
            run_id=self.context["run_id"],
            run_retry_id=self.context["run_retry_id"],
            action_id=self.context["action_id"]
        )
        self._set_key_value(node, key, value)

    def set_candidate_value(self, key: str, value):
        required = [
            "workflow_id", "sample_id", "rerun_id",
            "run_id", "run_retry_id", "action_id", "candidate_id"
        ]
        for r in required:
            if self.context[r] is None:
                raise ValueError(f"Context '{r}' must be set before setting candidate value.")
        node = self._create_node_if_needed(
            workflow_id=self.context["workflow_id"],
            sample_id=self.context["sample_id"],
            rerun_id=self.context["rerun_id"],
            run_id=self.context["run_id"],
            run_retry_id=self.context["run_retry_id"],
            action_id=self.context["action_id"],
            candidate_id=self.context["candidate_id"]
        )
        self._set_key_value(node, key, value)

    # ---------------------------------------------------------------------
    # "Append to open_log" Methods (No IDs, uses context)
    # ---------------------------------------------------------------------
    def append_to_open_log_workflow(self, message: str):
        if self.context["workflow_id"] is None:
            raise ValueError("workflow_id must be set.")
        node = self._create_node_if_needed(
            workflow_id=self.context["workflow_id"]
        )
        self._set_key_value(node, "open_log", message)

    def append_to_open_log_sample(self, message: str):
        required = ["workflow_id", "sample_id"]
        for r in required:
            if self.context[r] is None:
                raise ValueError(f"'{r}' must be set before appending to sample's open_log.")
        node = self._create_node_if_needed(
            workflow_id=self.context["workflow_id"],
            sample_id=self.context["sample_id"]
        )
        self._set_key_value(node, "open_log", message)

    def append_to_open_log_rerun(self, message: str):
        required = ["workflow_id", "sample_id", "rerun_id"]
        for r in required:
            if self.context[r] is None:
                raise ValueError(f"'{r}' must be set before appending to rerun's open_log.")
        node = self._create_node_if_needed(
            workflow_id=self.context["workflow_id"],
            sample_id=self.context["sample_id"],
            rerun_id=self.context["rerun_id"]
        )
        self._set_key_value(node, "open_log", message)

    def append_to_open_log_run(self, message: str):
        required = ["workflow_id", "sample_id", "rerun_id", "run_id"]
        for r in required:
            if self.context[r] is None:
                raise ValueError(f"'{r}' must be set before appending to run's open_log.")
        node = self._create_node_if_needed(
            workflow_id=self.context["workflow_id"],
            sample_id=self.context["sample_id"],
            rerun_id=self.context["rerun_id"],
            run_id=self.context["run_id"]
        )
        self._set_key_value(node, "open_log", message)

    def append_to_open_log_run_retry(self, message: str):
        required = ["workflow_id", "sample_id", "rerun_id", "run_id", "run_retry_id"]
        for r in required:
            if self.context[r] is None:
                raise ValueError(f"'{r}' must be set before appending to run_retry's open_log.")
        node = self._create_node_if_needed(
            workflow_id=self.context["workflow_id"],
            sample_id=self.context["sample_id"],
            rerun_id=self.context["rerun_id"],
            run_id=self.context["run_id"],
            run_retry_id=self.context["run_retry_id"]
        )
        self._set_key_value(node, "open_log", message)

    def append_to_open_log_action(self, message: str):
        required = ["workflow_id", "sample_id", "rerun_id", "run_id", "run_retry_id", "action_id"]
        for r in required:
            if self.context[r] is None:
                raise ValueError(f"'{r}' must be set before appending to action's open_log.")
        node = self._create_node_if_needed(
            workflow_id=self.context["workflow_id"],
            sample_id=self.context["sample_id"],
            rerun_id=self.context["rerun_id"],
            run_id=self.context["run_id"],
            run_retry_id=self.context["run_retry_id"],
            action_id=self.context["action_id"]
        )
        self._set_key_value(node, "open_log", message)

    def append_to_open_log_candidate(self, message: str):
        required = [
            "workflow_id", "sample_id", "rerun_id",
            "run_id", "run_retry_id", "action_id", "candidate_id"
        ]
        for r in required:
            if self.context[r] is None:
                raise ValueError(f"'{r}' must be set before appending to candidate's open_log.")
        node = self._create_node_if_needed(
            workflow_id=self.context["workflow_id"],
            sample_id=self.context["sample_id"],
            rerun_id=self.context["rerun_id"],
            run_id=self.context["run_id"],
            run_retry_id=self.context["run_retry_id"],
            action_id=self.context["action_id"],
            candidate_id=self.context["candidate_id"]
        )
        self._set_key_value(node, "open_log", message)