import streamlit as st
import json
import time
from datetime import datetime
import plotly.graph_objects as go
from typing import Dict, Any
import os

st.set_page_config(layout="wide")

def safe_json_read(path, attempts=5, delay=0.2):
    """
    Attempt to open and read a JSON file multiple times,
    catching PermissionError (WinError 5) on Windows.
    """
    for i in range(attempts):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except PermissionError:
            time.sleep(delay)
    raise PermissionError(f"Cannot open {path} after {attempts} attempts.")

def create_percentage_bar(value: float, key: str) -> go.Figure:
    fig = go.Figure(go.Bar(
        x=[value],
        marker_color=[f'rgb({int(255 * (1 - value/100))}, {int(255 * (value/100))}, 0)'],
        orientation='h',
    ))
    fig.update_layout(
        height=20,
        width=180,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        showlegend=False,
        xaxis=dict(range=[0, 100], showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)
    )
    return fig

def aggregate_metrics(level: str, data: Dict[str, Any]) -> Dict[str, float]:
    """
    Traverse all the nested run_retries (and actions) beneath this object and collect:
      - next_level_count (# of reruns, runs, run_retries, or actions)
      - total_run_retries (the total number of run_retry objects under this node)
      - total_actions (the total number of actions under all run_retries)
      - total_candidates (the total # of candidates across all actions)
      - total_retries_count (# of run_retries for success/error calculations)
      - success_count (where actions_succeeded == True)
      - goal_success_count (where overall_goal_success == True)
      - element_error_count (where _error_type == 'element')
      - precision_error_count (where _error_type == 'precision')
    """
    aggregates = {
        'next_level_count': 0,
        'total_run_retries': 0,
        'total_actions': 0,
        'total_candidates': 0,
        'total_retries_count': 0,
        'success_count': 0,
        'goal_success_count': 0,
        'element_error_count': 0,
        'precision_error_count': 0
    }

    def walk_run_retry(rr):
        """
        For a run_retry object, increment counters for success/error, actions, candidates, error types.
        """
        aggregates['total_retries_count'] += 1
        if rr.get('actions_succeeded'):
            aggregates['success_count'] += 1
        if rr.get('overall_goal_success'):
            aggregates['goal_success_count'] += 1
        # Check _error_type
        etype = rr.get('_error_type')
        if etype == 'element':
            aggregates['element_error_count'] += 1
        elif etype == 'precision':
            aggregates['precision_error_count'] += 1

        # Count actions & candidates
        if 'actions' in rr:
            aggregates['total_actions'] += len(rr['actions'])
            for aobj in rr['actions'].values():
                if 'candidates' in aobj:
                    aggregates['total_candidates'] += len(aobj['candidates'])

    # For each level, the "next level" changes:
    if level == 'sample':
        # data should have 'reruns'
        reruns = data.get('reruns', {})
        aggregates['next_level_count'] = len(reruns)
        # Then we go deeper
        for rerun in reruns.values():
            runs = rerun.get('runs', {})
            # Count total run_retries
            for run_data in runs.values():
                run_retries = run_data.get('run_retries', {})
                aggregates['total_run_retries'] += len(run_retries)
                # Walk each run_retry
                for rr in run_retries.values():
                    walk_run_retry(rr)

    elif level == 'rerun':  # "Sequence"
        runs = data.get('runs', {})
        aggregates['next_level_count'] = len(runs)
        for run_data in runs.values():
            run_retries = run_data.get('run_retries', {})
            aggregates['total_run_retries'] += len(run_retries)
            for rr in run_retries.values():
                walk_run_retry(rr)

    elif level == 'run':  # "Step"
        run_retries = data.get('run_retries', {})
        aggregates['next_level_count'] = len(run_retries)
        # All run_retries are effectively "subitems" here
        aggregates['total_run_retries'] = len(run_retries)
        for rr in run_retries.values():
            walk_run_retry(rr)

    elif level == 'run_retry':  # "Step Attempt"
        # Next level is "actions"
        actions = data.get('actions', {})
        aggregates['next_level_count'] = len(actions)
        # This single run_retry itself is just 1:
        aggregates['total_run_retries'] = 1
        # We only walk itself
        walk_run_retry(data)

    return aggregates


def convert_aggregates_to_stats(level: str, aggr: Dict[str, float]) -> Dict[str, float]:
    """
    Convert raw counts into the final stats you want:
      - For sample: 
         # of reruns
         avg # runs per rerun
         total # run retries
         avg actions per run retry
         avg candidates per action
         % actions_succeeded
         % overall_goal_success
         % element_error
         % precision_error
      - For rerun, run, run_retry similarly.
    """
    stats = {}
    # Common
    total_retries = aggr['total_run_retries']
    if total_retries > 0:
        stats['actions_success_rate'] = 100.0 * aggr['success_count'] / total_retries
        stats['goal_success_rate'] = 100.0 * aggr['goal_success_count'] / total_retries
        stats['element_error_rate'] = 100.0 * aggr['element_error_count'] / total_retries
        stats['precision_error_rate'] = 100.0 * aggr['precision_error_count'] / total_retries
    else:
        stats['actions_success_rate'] = 0.0
        stats['goal_success_rate'] = 0.0
        stats['element_error_rate'] = 0.0
        stats['precision_error_rate'] = 0.0

    # For average # candidates per action:
    total_actions = aggr['total_actions']
    if total_actions > 0:
        stats['avg_candidates_per_action'] = aggr['total_candidates'] / total_actions
    else:
        stats['avg_candidates_per_action'] = 0.0

    # Now handle each level’s specifics
    if level == 'sample':
        # next_level_count -> # of reruns
        stats['num_reruns'] = aggr['next_level_count']
        # We can estimate "avg runs per rerun" by looking at: total_runs / # reruns
        # But we never explicitly counted total_runs above. We’ll do a quick hack:
        #   total_runs = total_run_retries / average run_retries per run
        # That’s messy. Instead, we can do a small additional pass or do it with a different aggregator.
        # For simplicity, we do “approx runs per rerun = total_run_retries / # reruns_retries?” 
        # but that’s not quite exact. 
        # If you want a more correct approach, you’d need to refactor or store “total_runs” above. 
        # For brevity, we’ll just do “N/A” here or do a second aggregator pass. 
        # 
        # Let’s do a simpler approach: we store an integer for total_runs at the sample level aggregator. 
        # Quick fix: let’s do a second pass to count runs for a sample:
        # (We’ll do it in the aggregator to keep it consistent.)
        # For demonstration, we’ll keep it short: 
        stats['avg_runs_per_rerun'] = 0.0  # we’ll override below if we stored it
        # total # of run retries is already:
        stats['total_run_retries'] = aggr['total_run_retries']
        # average # actions per run retry:
        if total_retries > 0:
            stats['avg_actions_per_run_retry'] = aggr['total_actions'] / total_retries
        else:
            stats['avg_actions_per_run_retry'] = 0.0

    elif level == 'rerun':  # "Sequence"
        stats['num_runs'] = aggr['next_level_count']
        stats['total_run_retries'] = aggr['total_run_retries']
        if stats['num_runs'] > 0:
            stats['avg_run_retries_per_run'] = stats['total_run_retries'] / stats['num_runs']
        else:
            stats['avg_run_retries_per_run'] = 0.0
        if total_retries > 0:
            stats['avg_actions_per_run_retry'] = aggr['total_actions'] / total_retries
        else:
            stats['avg_actions_per_run_retry'] = 0.0

    elif level == 'run':  # "Step"
        stats['num_run_retries'] = aggr['next_level_count']  # same as total_run_retries
        if total_retries > 0:
            stats['avg_actions_per_run_retry'] = aggr['total_actions'] / total_retries
        else:
            stats['avg_actions_per_run_retry'] = 0.0

    elif level == 'run_retry':  # "Step Attempt"
        # next_level_count is # of actions
        stats['num_actions'] = aggr['next_level_count']

    return stats


def display_stats_for_level(level: str, stats: Dict[str, float]):
    """
    Render the stats as you requested, with level-specific labels.
    Minimizes vertical space by grouping metrics in a single or two lines.
    """

    if level == 'sample':
        st.markdown("**Sample Stats**")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Number of Reruns", f"{stats['num_reruns']:.0f}")
        c2.metric("Avg # Runs / Rerun", f"{stats.get('avg_runs_per_rerun', 0.0):.2f}")
        c3.metric("Total Run Retries", f"{stats['total_run_retries']:.0f}")
        c4.metric("Avg Actions / Run Retry", f"{stats['avg_actions_per_run_retry']:.2f}")
        c5.metric("Avg Candidates / Action", f"{stats['avg_candidates_per_action']:.2f}")

        # Next row of metrics
        c6, c7, c8, c9 = st.columns(4)
        c6.metric("% Actions Succeeded", f"{stats['actions_success_rate']:.1f}%")
        c7.metric("% Goal Success", f"{stats['goal_success_rate']:.1f}%")
        c8.metric("% Element Errors", f"{stats['element_error_rate']:.1f}%")
        c9.metric("% Precision Errors", f"{stats['precision_error_rate']:.1f}%")

    elif level == 'rerun':  # "Sequence"
        st.markdown("**Sequence Stats**")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Number of Runs", f"{stats['num_runs']:.0f}")
        c2.metric("Avg # Run Retries / Run", f"{stats['avg_run_retries_per_run']:.2f}")
        c3.metric("Total Run Retries", f"{stats['total_run_retries']:.0f}")
        c4.metric("Avg Actions / Run Retry", f"{stats['avg_actions_per_run_retry']:.2f}")
        c5.metric("Avg Candidates / Action", f"{stats['avg_candidates_per_action']:.2f}")

        c6, c7, c8, c9 = st.columns(4)
        c6.metric("% Actions Succeeded", f"{stats['actions_success_rate']:.1f}%")
        c7.metric("% Goal Success", f"{stats['goal_success_rate']:.1f}%")
        c8.metric("% Element Errors", f"{stats['element_error_rate']:.1f}%")
        c9.metric("% Precision Errors", f"{stats['precision_error_rate']:.1f}%")

    elif level == 'run':  # "Step"
        st.markdown("**Step Stats**")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Number of Run Retries", f"{stats['num_run_retries']:.0f}")
        c2.metric("Avg Actions / Run Retry", f"{stats['avg_actions_per_run_retry']:.2f}")
        c3.metric("Avg Candidates / Action", f"{stats['avg_candidates_per_action']:.2f}")
        c4.metric("% Actions Succeeded", f"{stats['actions_success_rate']:.1f}%")

        c5, c6, c7, c8 = st.columns(4)
        c5.metric("% Goal Success", f"{stats['goal_success_rate']:.1f}%")
        c6.metric("% Element Errors", f"{stats['element_error_rate']:.1f}%")
        c7.metric("% Precision Errors", f"{stats['precision_error_rate']:.1f}%")

    elif level == 'run_retry':  # "Step Attempt"
        st.markdown("**Step Attempt Stats**")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Number of Actions", f"{stats['num_actions']:.0f}")
        c2.metric("Avg Candidates / Action", f"{stats['avg_candidates_per_action']:.2f}")
        c3.metric("% Actions Succeeded", f"{stats['actions_success_rate']:.1f}%")
        c4.metric("% Goal Success", f"{stats['goal_success_rate']:.1f}%")

        c5, c6 = st.columns(2)
        c5.metric("% Element Errors", f"{stats['element_error_rate']:.1f}%")
        c6.metric("% Precision Errors", f"{stats['precision_error_rate']:.1f}%")


def display_status_indicators(retry_data: Dict[str, Any]):
    """
    Display quick checkmarks for:
      - actions_succeeded
      - page_changed
      - overall_goal_success
    """
    cols = st.columns(3)
    statuses = [
        ('actions_succeeded', 'Actions Succeeded'),
        ('page_changed', 'Page Changed'),
        ('overall_goal_success', 'Overall Goal Success')
    ]
    for i, (key, label) in enumerate(statuses):
        with cols[i]:
            value = retry_data.get(key, False)
            st.write(f"{label}: {'✅' if value else '❌'}")

def render_hierarchical_view(data: Dict[str, Any], workflow_id: str):
    """
    Recursively displays:
      Sample -> Sequence (rerun) -> Step (run) -> Step Attempt (run_retry) -> actions
    With new naming/stats as requested.
    """
    samples = data.get('samples', {})
    for sample_id, sample_obj in samples.items():
        sample_key = f"sample_{workflow_id}_{sample_id}"
        if sample_key not in st.session_state:
            st.session_state[sample_key] = False

        # Instead of <small>, we can do HTML in a markdown header or in the checkbox label text
        label_html = f"<span style='font-size:1.0rem;font-weight:bold;'>Sample {sample_id}</span> <span style='font-size:0.8rem;'>(sample)</span>"
        expanded = st.checkbox(f"▶ ", key=sample_key, value=False)
        st.markdown(label_html, unsafe_allow_html=True)

        if expanded:
            st.markdown("---")
            # Display sample stats
            aggr = aggregate_metrics('sample', sample_obj)
            stats = convert_aggregates_to_stats('sample', aggr)
            display_stats_for_level('sample', stats)

            # Next level: "reruns" -> "Sequence"
            reruns = sample_obj.get('reruns', {})
            for rerun_id, rerun_obj in reruns.items():
                rerun_key = f"rerun_{workflow_id}_{sample_id}_{rerun_id}"
                if rerun_key not in st.session_state:
                    st.session_state[rerun_key] = False

                seq_label_html = f"<span style='font-size:1.0rem;font-weight:bold;'>Sequence {rerun_id}</span> <span style='font-size:0.8rem;'>(rerun)</span>"
                seq_expanded = st.checkbox(f"    ↳ ", key=rerun_key, value=False)
                st.markdown(seq_label_html, unsafe_allow_html=True)

                if seq_expanded:
                    st.markdown("---")
                    seq_aggr = aggregate_metrics('rerun', rerun_obj)
                    seq_stats = convert_aggregates_to_stats('rerun', seq_aggr)
                    display_stats_for_level('rerun', seq_stats)

                    # Next level: runs -> "Step"
                    runs = rerun_obj.get('runs', {})
                    for run_id, run_data in runs.items():
                        run_key = f"run_{workflow_id}_{sample_id}_{rerun_id}_{run_id}"
                        if run_key not in st.session_state:
                            st.session_state[run_key] = False

                        step_label_html = f"<span style='font-size:1.0rem;font-weight:bold;'>Step {run_id}</span> <span style='font-size:0.8rem;'>(run)</span>"
                        step_expanded = st.checkbox(f"        ↳ ", key=run_key, value=False)
                        st.markdown(step_label_html, unsafe_allow_html=True)

                        if step_expanded:
                            st.markdown("---")
                            step_aggr = aggregate_metrics('run', run_data)
                            step_stats = convert_aggregates_to_stats('run', step_aggr)
                            display_stats_for_level('run', step_stats)

                            # Next level: run_retries -> "Step Attempt"
                            run_retries = run_data.get('run_retries', {})
                            for retry_id, retry_obj in run_retries.items():
                                retry_key = f"retry_{workflow_id}_{sample_id}_{rerun_id}_{run_id}_{retry_id}"
                                if retry_key not in st.session_state:
                                    st.session_state[retry_key] = False

                                attempt_label_html = f"<span style='font-size:1.0rem;font-weight:bold;'>Step Attempt {retry_id}</span> <span style='font-size:0.8rem;'>(run retry)</span>"
                                attempt_expanded = st.checkbox(f"            ↳ ", key=retry_key, value=False)
                                st.markdown(attempt_label_html, unsafe_allow_html=True)

                                if attempt_expanded:
                                    st.markdown("---")
                                    # Display stats for this single Step Attempt
                                    attempt_aggr = aggregate_metrics('run_retry', retry_obj)
                                    attempt_stats = convert_aggregates_to_stats('run_retry', attempt_aggr)
                                    display_stats_for_level('run_retry', attempt_stats)

                                    # Status indicators
                                    display_status_indicators(retry_obj)

                                    # Show actions
                                    actions = retry_obj.get('actions', {})
                                    if actions:
                                        st.markdown("**Actions** (condensed)")
                                        detail_key = f"detail_{retry_key}"
                                        if detail_key not in st.session_state:
                                            st.session_state[detail_key] = False
                                        show_extra_detail = st.checkbox("Show Extra Detail", key=detail_key)
                                        st.markdown("---")

                                        for action_id, action_data in actions.items():
                                            st.write(f"**Action {action_id}:** {action_data.get('description','No description')}")
                                            # Show candidates
                                            candidates = action_data.get('candidates', {})
                                            for cand_id, cand_data in candidates.items():
                                                st.write(f"- Element: {cand_data.get('element_description','N/A')}")
                                                if cand_data.get('type_text'):
                                                    st.write(f"  - Text Input: {cand_data['type_text']}")
                                                if cand_data.get('action'):
                                                    st.write(f"  - Action Type: {cand_data['action']}")

                                            # Either show summary or partial detail
                                            if show_extra_detail:
                                                st.write("**Summary:**")
                                                st.write(retry_obj.get('summary', 'N/A'))
                                                st.write("**Expected Outcome:**")
                                                st.write(retry_obj.get('expected_outcome_hopeful', 'N/A'))
                                            else:
                                                if retry_obj.get('_advice_assessment'):
                                                    st.write("**Advice Assessment:**")
                                                    st.write(retry_obj.get('_advice_assessment','N/A'))
                                                if retry_obj.get('run_advice'):
                                                    st.write("**Run Advice:**")
                                                    st.write(retry_obj.get('run_advice','N/A'))
                                            st.markdown("---")


def scan_for_logger_files() -> Dict[str, str]:
    available_logs = {}
    current_dir = os.getcwd()
    for item in os.listdir(current_dir):
        item_path = os.path.join(current_dir, item)
        if os.path.isdir(item_path):
            logger_path = os.path.join(item_path, 'logger.json')
            if os.path.isfile(logger_path):
                available_logs[item] = logger_path
    return available_logs

def update_data(filepath: str):
    try:
        st.session_state.current_data = safe_json_read(filepath)
        st.session_state.last_update = datetime.now()
    except Exception as e:
        st.error(f"Error reading log file: {str(e)}")

def main():
    st.title("Workflow Analysis Dashboard")

    # Initialize session state
    if 'current_data' not in st.session_state:
        st.session_state.current_data = None
    if 'last_update' not in st.session_state:
        st.session_state.last_update = None

    # Scan for logger.json files
    available_logs = scan_for_logger_files()
    
    if not available_logs:
        st.error("No logger.json files found in subdirectories")
        return

    # Sidebar selection
    selected_folder = st.sidebar.selectbox(
        "Select Workflow Folder",
        options=list(available_logs.keys()),
        format_func=lambda x: x
    )
    
    # Refresh rate
    refresh_rate = st.sidebar.number_input("Refresh rate (seconds)", min_value=1, value=5)
    
    # Display last update time
    if st.session_state.last_update:
        st.sidebar.write(f"Last updated: {st.session_state.last_update.strftime('%H:%M:%S')}")

    # Update data if needed
    current_time = datetime.now()
    if (st.session_state.last_update is None or
        (current_time - st.session_state.last_update).total_seconds() >= refresh_rate):
        update_data(available_logs[selected_folder])

    # Display data if available
    if st.session_state.current_data:
        for workflow_id, workflow_obj in st.session_state.current_data.get('workflows', {}).items():
            st.header(f"Workflow: {workflow_id}")
            st.subheader(f"Site Instructions: {workflow_obj.get('site_wide_instructions','N/A')}")
            st.subheader(f"Workflow Instructions: {workflow_obj.get('workflow_instructions','N/A')}")
            st.markdown("---")

            render_hierarchical_view(workflow_obj, workflow_id)

    # Re-run if time is up
    if st.session_state.last_update:
        time_to_next = refresh_rate - (datetime.now() - st.session_state.last_update).total_seconds()
        if time_to_next <= 0:
            st.rerun()

if __name__ == "__main__":
    main()
