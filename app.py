import streamlit as st
import pandas as pd
import sys
import io

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
    .instruction-text {
        font-size: 1.1em;
        font-weight: 500;
        color: #31333F;
        margin-bottom: 10px;
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

st.write("Upload your file to get started.")

# 1. UPLOAD
uploaded_file = st.file_uploader("Upload Excel/CSV", type=['xlsx', 'csv'])

if uploaded_file:
    file_type = 'csv' if uploaded_file.name.lower().endswith('.csv') else 'xlsx'
    
    # --- STEP 1: HEADER SELECTION (VISUAL) ---
    st.divider()
    st.markdown("### 1. Select Header Row")
    st.info("Look at the table below. Find the row that contains your column names (like 'Amount', 'Name').")
    
    # Read raw for preview
    uploaded_file.seek(0)
    if file_type == 'csv':
        raw_lines = uploaded_file.getvalue().decode('utf-8', errors='replace').splitlines()
        df_preview = pd.read_csv(io.StringIO('\n'.join(raw_lines[:20])), header=None)
    else:
        df_preview = pd.read_excel(uploaded_file, header=None, nrows=20)
    
    # Display Preview
    st.dataframe(df_preview, use_container_width=True)
    
    # Input for Header Row
    header_index = st.number_input(
        "Which Row Number (0, 1, 2...) contains the headers?", 
        min_value=0, 
        max_value=len(df_preview)-1, 
        value=0,
        step=1,
        help="Enter the bold number you see on the left side of the row."
    )
    
    # Reload Data with correct header
    uploaded_file.seek(0)
    if file_type == 'csv':
        df = pd.read_csv(uploaded_file, header=header_index)
        preamble_lines = raw_lines[:header_index]
        preamble_text = "\n".join(preamble_lines) + "\n" if preamble_lines else ""
    else:
        df = pd.read_excel(uploaded_file, header=header_index)
        df_preamble_excel = pd.read_excel(uploaded_file, header=None, nrows=header_index) if header_index > 0 else pd.DataFrame()

    # --- STEP 2: COLUMN SELECTION ---
    st.divider()
    st.markdown("### 2. Select Amount Column")
    
    col1, col2 = st.columns(2)
    with col1:
        # Auto-detect column
        amount_col_idx = 0
        for i, col in enumerate(df.columns):
            if "amt" in str(col).lower() or "amount" in str(col).lower():
                amount_col_idx = i
                break
        
        target_col = st.selectbox(
            "Select the column containing the Amounts:", 
            df.columns, 
            index=amount_col_idx
        )
        
    # Calculate
    df['__val__'] = df[target_col].apply(clean_currency)
    current_total = df['__val__'].sum()
    
    with col2:
        st.metric("Current Total", f"{current_total:,.2f}")

    # --- STEP 3: TARGET ---
    st.divider()
    st.markdown("### 3. Enter Target")
    
    desired_total = st.number_input("What is your Desired Total?", value=float(current_total), step=100.0)
    to_remove = current_total - desired_total
    
    if to_remove < -0.01:
        st.error("Desired total is higher than current! This tool removes rows to lower the total.")
    else:
        st.info(f"Target to remove: **{to_remove:,.2f}**")
        
        if st.button("Find Rows to Remove", type="primary"):
            if to_remove <= 0.01:
                st.success("Total is already correct!")
            else:
                with st.spinner("Calculating..."):
                    cands = [(i, v) for i, v in df['__val__'].items() if v > 0.01]
                    res = solve_closest(cands, to_remove)
                    
                    st.divider()
                    st.subheader("Results")
                    
                    c1, c2 = st.columns(2)
                    c1.metric("Target Removal", f"{to_remove:,.2f}")
                    c2.metric("Found Removal", f"{res['sum']:,.2f}")
                    
                    if not res['exact']:
                        diff = res['diff']
                        st.warning("⚠️ Exact match not found.")
                        st.markdown(f"""
                        <div class="step-box" style="border-left: 5px solid #0068c9;">
                            <strong>💡 How to Fix:</strong><br>
                            We found rows summing to <b>{res['sum']:,.2f}</b>.<br>
                            To match your target exactly, you need to remove an extra <b>{diff:,.2f}</b>.<br><br>
                            <u>Action:</u> <b>Subtract {diff:,.2f}</b> from the 'Amount' of one of the rows you are <b>KEEPING</b>.
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.success("✅ Exact match found!")
                        
                    # Prepare Download
                    df_keep = df.drop(index=res['indices']).copy()
                    if '__val__' in df_keep: del df_keep['__val__']
                    
                    # CLEAN HEADERS (Remove Unnamed)
                    clean_headers = []
                    for col in df_keep.columns:
                        if pd.isna(col) or str(col).strip() == "" or "Unnamed" in str(col):
                            clean_headers.append("")
                        else:
                            clean_headers.append(col)
                    df_keep.columns = clean_headers
                    
                    # GENERATE FILE
                    if file_type == 'csv':
                        csv_data = df_keep.to_csv(index=False)
                        final_content = preamble_text + csv_data
                        out_data = final_content.encode('utf-8')
                        fname = "fixed_file.csv"
                        mime = "text/csv"
                    else:
                        output = io.BytesIO()
                        # Use openpyxl engine
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            if header_index > 0:
                                df_preamble_excel.to_excel(writer, index=False, header=False, startrow=0)
                            df_keep.to_excel(writer, index=False, header=True, startrow=header_index)
                        out_data = output.getvalue()
                        fname = "fixed_file.xlsx"
                        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

                    st.download_button(
                        label="⬇️ Download Final File", 
                        data=out_data, 
                        file_name=fname, 
                        mime=mime, 
                        type="primary"
                    )
                    
                    st.caption(f"Removed {len(res['indices'])} rows.")
                    with st.expander("See removed rows"):
                        df_out = df.loc[res['indices']].copy()
                        if '__val__' in df_out: del df_out['__val__']
                        st.dataframe(df_out)
