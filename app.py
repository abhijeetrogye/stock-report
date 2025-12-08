import streamlit as st
import pandas as pd
import sys
import numpy as np
import time

# Increase recursion depth for deep search trees
sys.setrecursionlimit(20000)

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Stock Value Fixer Pro", layout="centered")

st.title("📊 Stock Value Correction Tool")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 10px;
    }
    .suggestion-box {
        background-color: #e8f4f9;
        border-left: 5px solid #0068c9;
        padding: 15px;
        margin: 10px 0;
    }
    </style>
""", unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---

def clean_currency(value):
    """Converts currency strings (e.g., '$1,234.56') to floats."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        # Remove currency symbols, commas, and spaces
        clean_str = value.replace(',', '').replace('$', '').replace('€', '').replace('£', '').replace(' ', '')
        try:
            return float(clean_str)
        except ValueError:
            return 0.0
    return 0.0

def solve_subset_sum_closest(candidates, target_val, max_steps=5000000):
    """
    Finds a subset of candidates that sums up to target_val (Exact) 
    OR finds the closest subset sum that is LESS THAN target_val (Approx).
    
    Args:
        candidates: List of tuples (original_index, value)
        target_val: The target sum to remove
        max_steps: Safety limit to prevent infinite hanging
        
    Returns:
        dict: {
            'indices': list of indices to remove,
            'sum': float (sum of removed items),
            'exact': bool,
            'diff': float,
            'status': str
        }
    """
    
    # 1. Convert to integers for precise calculation (avoid float issues)
    scale = 100
    candidates_int = [(idx, int(round(val * scale))) for idx, val in candidates]
    target_int = int(round(target_val * scale))
    
    # Sort descending for optimization
    candidates_int.sort(key=lambda x: x[1], reverse=True)
    
    values = [x[1] for x in candidates_int]
    total_available = sum(values)
    
    # Optimization: If total available is less than target
    if total_available <= target_int:
        return {
            'indices': [x[0] for x in candidates],
            'sum': total_available / scale,
            'exact': (total_available == target_int),
            'diff': (target_int - total_available) / scale,
            'status': 'All items taken (Total < Target)'
        }

    # Global best tracker
    best_solution = {
        'sum_int': 0,
        'indices': []
    }
    
    # Suffix sums for pruning
    suffix_sums = [0] * (len(values) + 1)
    for i in range(len(values) - 1, -1, -1):
        suffix_sums[i] = suffix_sums[i+1] + values[i]

    found_exact = False
    steps = 0

    def backtrack(index, current_sum, current_indices):
        nonlocal found_exact, steps
        steps += 1
        
        # Safety break
        if steps > max_steps:
            return

        if found_exact: return
        
        # Check if we hit the target exactly
        if current_sum == target_int:
            best_solution['sum_int'] = current_sum
            best_solution['indices'] = list(current_indices)
            found_exact = True
            return

        # If we exceeded target
        if current_sum > target_int:
            return

        # Update best solution found so far (Maximize sum <= target)
        if current_sum > best_solution['sum_int']:
            best_solution['sum_int'] = current_sum
            best_solution['indices'] = list(current_indices)

        # Stop if no more candidates
        if index >= len(candidates_int):
            return

        # Pruning: If current_sum + all remaining items <= best_solution['sum_int']
        if current_sum + suffix_sums[index] <= best_solution['sum_int']:
            return

        # Recurse: Include current item
        if current_sum + values[index] <= target_int:
            current_indices.append(candidates_int[index][0])
            backtrack(index + 1, current_sum + values[index], current_indices)
            current_indices.pop()
        
        # Recurse: Exclude current item
        backtrack(index + 1, current_sum, current_indices)

    # Start solver
    backtrack(0, 0, [])
    
    final_sum = best_solution['sum_int'] / scale
    diff = (target_int - best_solution['sum_int']) / scale
    
    status = 'Exact' if found_exact else 'Approximate'
    if steps > max_steps:
        status += ' (Time Limit Reached)'
        
    return {
        'indices': best_solution['indices'],
        'sum': final_sum,
        'exact': found_exact,
        'diff': diff,
        'status': status
    }

# --- MAIN APP LOGIC ---

st.info("👋 Welcome! Upload your file and follow the steps below.")

# 1. File Upload
st.header("1. Upload Data & Settings")
uploaded_file = st.file_uploader("Upload Excel or CSV file", type=['xlsx', 'csv'])

if uploaded_file:
    # PROBLEM 3 SOLUTION: Header Row Selection
    col_h1, col_h2 = st.columns([1, 2])
    with col_h1:
        header_row = st.number_input(
            "Header Row Number", 
            min_value=0, 
            value=0, 
            help="Row number where column names are located (0-based). Increase this if columns look wrong (e.g. Unnamed: 0)."
        )
    
    try:
        # Load data with specified header
        if uploaded_file.name.endswith('.csv'):
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, header=header_row)
        else:
            uploaded_file.seek(0)
            df = pd.read_excel(uploaded_file, header=header_row)
            
        st.write("Preview of loaded data:")
        st.dataframe(df.head())
        
        # PROBLEM 2 SOLUTION: Column Selection
        st.header("2. Configure Target")
        
        all_cols = df.columns.tolist()
        
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            target_col = st.selectbox(
                "Select the 'Amount' Column", 
                options=all_cols,
                index=0,
                help="Choose the column containing the values you want to sum/remove."
            )
            
        # Clean the selected column
        df['__calc_value__'] = df[target_col].apply(clean_currency)
        
        # Filter out rows with 0 or NaN values for calculation purposes
        # (We keep them in df, but candidates must be positive)
        
        current_total = df['__calc_value__'].sum()
        
        with col_s2:
            st.metric("Current Total Amount", f"{current_total:,.2f}")
            
        desired_total = st.number_input(
            "Enter Desired Target Total", 
            min_value=0.0, 
            value=float(current_total),
            step=100.0,
            format="%.2f"
        )
        
        remove_amount = current_total - desired_total
        
        if remove_amount < -0.01: # Tolerance for float
            st.error("Desired total is higher than current total! This tool is for REMOVING rows to lower the total.")
        else:
            st.markdown(f"### Target to Remove: `{remove_amount:,.2f}`")
            
            if st.button("Find Rows to Remove", type="primary"):
                if remove_amount <= 0.01:
                    st.warning("Nothing to remove.")
                else:
                    with st.spinner("Calculating optimal combination..."):
                        # Prepare candidates
                        candidates = []
                        # Only consider positive values
                        for idx, val in df['__calc_value__'].items():
                            if val > 0.01:
                                candidates.append((idx, val))
                        
                        # Run Solver
                        result = solve_subset_sum_closest(candidates, remove_amount)
                        
                        # Process Result
                        indices_to_remove = result['indices']
                        actual_removed_sum = result['sum']
                        is_exact = result['exact']
                        difference = result['diff']
                        status = result['status']
                        
                        # --- DISPLAY RESULTS ---
                        st.divider()
                        st.subheader("Calculation Results")
                        
                        col_r1, col_r2, col_r3 = st.columns(3)
                        col_r1.metric("Target Removal", f"{remove_amount:,.2f}")
                        col_r2.metric("Actual Found Removal", f"{actual_removed_sum:,.2f}")
                        col_r3.metric("Difference (Short by)", f"{difference:,.2f}")
                        
                        # PROBLEM 1 SOLUTION: Suggestion Logic
                        if not is_exact:
                            st.warning(f"⚠️ Exact match not found. ({status})")
                            if difference > 0:
                                st.markdown(
                                    f"""
                                    <div class="suggestion-box">
                                        <strong>💡 Suggestion to Fix:</strong><br>
                                        We found a combination summing to <b>{actual_removed_sum:,.2f}</b>.<br>
                                        You are short by <b>{difference:,.2f}</b>.<br><br>
                                        <u>Recommended Action:</u><br> 
                                        Select one of the rows below (to be removed) and <b>INCREASE its amount by {difference:,.2f}</b>.
                                        Then the total removed will match your target exactly.
                                    </div>
                                    """, unsafe_allow_html=True
                                )
                            else:
                                st.info("Difference is negligible.")
                        else:
                            st.success("✅ Exact match found!")

                        # Create Result Dataframes
                        df_removed = df.loc[indices_to_remove].copy()
                        df_kept = df.drop(index=indices_to_remove).copy()
                        
                        # Clean up
                        if '__calc_value__' in df_removed.columns:
                            del df_removed['__calc_value__']
                        if '__calc_value__' in df_kept.columns:
                            del df_kept['__calc_value__']
                        
                        # Show Removed Rows
                        st.write(f"**{len(df_removed)} rows to remove:**")
                        st.dataframe(df_removed)
                            
                        # Download Button
                        st.subheader("⬇️ Download Final File")
                        csv_kept = df_kept.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 Download Cleaned File (Rows Removed)",
                            data=csv_kept,
                            file_name="cleaned_stock_list.csv",
                            mime="text/csv",
                            type="primary"
                        )

    except Exception as e:
        st.error(f"An error occurred: {e}")
        st.info("Tip: Try changing the 'Header Row Number' if the preview looks empty or incorrect.")
