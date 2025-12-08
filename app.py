import streamlit as st
import pandas as pd
import sys
import numpy as np

# Increase recursion depth
sys.setrecursionlimit(20000)

st.set_page_config(page_title="Stock Fixer", layout="centered")
st.title("📊 Simple Stock Fixer")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .step-box {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        padding: 15px;
        border-radius: 5px;
        margin-bottom: 20px;
    }
    .success-box {
        background-color: #d4edda;
        color: #155724;
        padding: 15px;
        border-radius: 5px;
        margin-top: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
def clean_currency(value):
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        clean_str = value.replace(',', '').replace('$', '').replace('€', '').replace('£', '').replace(' ', '')
        try:
            return float(clean_str)
        except ValueError:
            return 0.0
    return 0.0

def solve_closest(candidates, target_val, max_steps=5000000):
    scale = 100
    candidates_int = [(idx, int(round(val * scale))) for idx, val in candidates]
    target_int = int(round(target_val * scale))
    candidates_int.sort(key=lambda x: x[1], reverse=True)
    
    values = [x[1] for x in candidates_int]
    total_available = sum(values)
    
    if total_available <= target_int:
        return {'indices': [x[0] for x in candidates], 'sum': total_available/scale, 'exact': total_available==target_int, 'diff': (target_int-total_available)/scale}

    best_sol = {'sum': 0, 'indices': []}
    suffix_sums = [0] * (len(values) + 1)
    for i in range(len(values) - 1, -1, -1):
        suffix_sums[i] = suffix_sums[i+1] + values[i]

    found_exact = False
    steps = 0

    def backtrack(idx, current_sum, current_indices):
        nonlocal found_exact, steps
        steps += 1
        if steps > max_steps or found_exact: return
        
        if current_sum == target_int:
            best_sol['sum'] = current_sum
            best_sol['indices'] = list(current_indices)
            found_exact = True
            return

        if current_sum > target_int: return

        if current_sum > best_sol['sum']:
            best_sol['sum'] = current_sum
            best_sol['indices'] = list(current_indices)

        if idx >= len(candidates_int): return
        if current_sum + suffix_sums[idx] <= best_sol['sum']: return

        if current_sum + values[idx] <= target_int:
            current_indices.append(candidates_int[idx][0])
            backtrack(idx + 1, current_sum + values[idx], current_indices)
            current_indices.pop()
        
        backtrack(idx + 1, current_sum, current_indices)

    backtrack(0, 0, [])
    
    return {
        'indices': best_sol['indices'],
        'sum': best_sol['sum'] / scale,
        'exact': found_exact,
        'diff': (target_int - best_sol['sum']) / scale
    }

# --- APP ---

st.write("Upload your file. We'll help you find the rows to remove.")

# 1. UPLOAD
uploaded_file = st.file_uploader("Upload Excel/CSV", type=['xlsx', 'csv'])

if uploaded_file:
    # --- STEP 1: VISUAL HEADER SELECTION ---
    st.markdown("### Step 1: Where are the column names?")
    
    # Read raw to show preview
    if uploaded_file.name.endswith('.csv'):
        df_raw = pd.read_csv(uploaded_file, header=None, nrows=10)
    else:
        df_raw = pd.read_excel(uploaded_file, header=None, nrows=10)
    
    # Create friendly options
    options = []
    for i in range(len(df_raw)):
        # Get first 3 non-empty values to show as preview
        row_values = [str(x) for x in df_raw.iloc[i].dropna().values]
        preview_text = ", ".join(row_values[:4])
        if len(preview_text) > 50: preview_text = preview_text[:50] + "..."
        options.append(f"Row {i+1}:  {preview_text}")
        
    selected_option = st.selectbox(
        "Look at the file preview. Which row contains headers like 'Amount', 'Name'?", 
        options,
        index=0
    )
    
    header_index = options.index(selected_option)
    
    # Reload with correct header
    uploaded_file.seek(0)
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file, header=header_index)
    else:
        df = pd.read_excel(uploaded_file, header=header_index)

    st.write("---")
    
    # --- STEP 2: COLUMN SELECTION ---
    st.markdown("### Step 2: What is the target?")
    
    col1, col2 = st.columns(2)
    with col1:
        # Try to auto-select column with 'amount' in name
        amount_col_idx = 0
        for i, col in enumerate(df.columns):
            if "amt" in str(col).lower() or "amount" in str(col).lower():
                amount_col_idx = i
                break
                
        target_col = st.selectbox("Select the Column with Amounts:", df.columns, index=amount_col_idx)
        
    # Clean data
    df['__val__'] = df[target_col].apply(clean_currency)
    current_total = df['__val__'].sum()
    
    with col2:
        st.metric("Current Total", f"{current_total:,.2f}")
        
    desired_total = st.number_input("Enter Desired Total:", value=float(current_total), step=100.0)
    
    to_remove = current_total - desired_total
    
    if to_remove < -0.01:
        st.error("Desired total is higher than current! You need to remove rows, not add them.")
    else:
        st.info(f"Need to remove: **{to_remove:,.2f}**")
        
        if st.button("Find Rows to Remove", type="primary"):
            if to_remove <= 0.01:
                st.success("Total is already correct!")
            else:
                with st.spinner("Calculating..."):
                    # Candidates
                    cands = [(i, v) for i, v in df['__val__'].items() if v > 0.01]
                    res = solve_closest(cands, to_remove)
                    
                    st.write("---")
                    st.subheader("Results")
                    
                    col_r1, col_r2 = st.columns(2)
                    col_r1.metric("Target Removal", f"{to_remove:,.2f}")
                    col_r2.metric("Found Removal", f"{res['sum']:,.2f}")
                    
                    if not res['exact']:
                        diff = res['diff']
                        st.warning("⚠️ Exact match not found.")
                        st.markdown(f"""
                        <div class="step-box" style="border-left: 5px solid orange;">
                            <strong>💡 Simple Fix:</strong><br>
                            We found rows summing to <b>{res['sum']:,.2f}</b>.<br>
                            You are still short by <b>{diff:,.2f}</b>.<br>
                            Just <b>add {diff:,.2f}</b> to one of the rows below before deleting it.
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.success("✅ Exact match found!")
                        
                    # Show dataframe
                    df_out = df.loc[res['indices']].copy()
                    if '__val__' in df_out: del df_out['__val__']
                    
                    st.write("Rows to remove:")
                    st.dataframe(df_out)
                    
                    # Download
                    df_keep = df.drop(index=res['indices']).copy()
                    if '__val__' in df_keep: del df_keep['__val__']
                    
                    csv = df_keep.to_csv(index=False).encode('utf-8')
                    st.download_button("⬇️ Download Final File", csv, "cleaned_file.csv", "text/csv", type="primary")
