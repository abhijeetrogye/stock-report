import streamlit as st
import pandas as pd
import sys

# Increase recursion depth just in case
sys.setrecursionlimit(5000)

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Stock Value Fixer", layout="centered")

st.title("📊 Stock Value Correction Tool")

# --- INITIALIZE SESSION STATE ---
if 'solution_indices' not in st.session_state:
    st.session_state.solution_indices = None
if 'processed_df' not in st.session_state:
    st.session_state.processed_df = None

# --- ⚠️ ALERT MESSAGE ---
st.warning(
    """
    **⚠️ IMPORTANT INSTRUCTIONS:**
    1. **Column Name:** Your file MUST have a column named strictly **'Amount'**.
    2. **No Total Row:** Do NOT include a 'Grand Total' row at the bottom of your Excel sheet. The tool calculates the total automatically.
    """
)

st.write("Upload your Stock List Excel/CSV, enter the desired total, and this tool will tell you exactly which rows to remove.")

# --- 1. FILE UPLOAD ---
uploaded_file = st.file_uploader("Upload Excel or CSV file", type=['xlsx', 'csv'])

def load_data(file):
    try:
        if file.name.endswith('.csv'):
            return pd.read_csv(file)
        else:
            return pd.read_excel(file)
    except Exception as e:
        st.error(f"Error reading file: {e}")
        return None

# --- CORE SOLVER ALGORITHM ---
def solve_subset_sum(candidates, target_int):
    # candidates is a list of tuples: (index, amount_int)
    # Sort descending for better pruning
    candidates.sort(key=lambda x: x[1], reverse=True)
    
    values = [x[1] for x in candidates]
    
    # Pre-calculate suffix sums for optimization
    suffix_sums = [0] * (len(values) + 1)
    for i in range(len(values) - 1, -1, -1):
        suffix_sums[i] = suffix_sums[i+1] + values[i]
        
    result_indices = []
    
    def backtrack(index, current_target):
        if current_target == 0:
            return True
        if index >= len(candidates) or current_target < 0:
            return False
        if suffix_sums[index] < current_target:
            return False
            
        current_val = candidates[index][1]
        current_idx = candidates[index][0]
        
        # Branch 1: Include this number
        if current_val <= current_target:
            result_indices.append(current_idx)
            if backtrack(index + 1, current_target - current_val):
                return True
            result_indices.pop() 
            
        # Branch 2: Skip this number
        if backtrack(index + 1, current_target):
            return True
            
        return False

    if backtrack(0, target_int):
        return result_indices
    else:
        return None

# --- MAIN APP LOGIC ---
if uploaded_file is not None:
    # Read file every rerun to ensure index consistency
    df = load_data(uploaded_file)
    
    if df is not None:
        if 'Amount' not in df.columns:
            st.error("❌ Error: The file does not have a column named 'Amount'. Please rename your column and try again.")
        else:
            # Pre-process
            df['Amount_Clean'] = pd.to_numeric(df['Amount'], errors='coerce')
            df_clean = df.dropna(subset=['Amount_Clean']).copy()
            df_clean['Amount_Int'] = (df_clean['Amount_Clean'] * 100).round().astype(int)
            
            # Store processed DF in session state
            st.session_state.processed_df = df
            
            current_total = df_clean['Amount_Clean'].sum()
            current_total_int = df_clean['Amount_Int'].sum()
            
            st.success(f"File Loaded! Total Rows: {len(df_clean)}")
            st.metric(label="Current Total Amount (Auto-Calculated)", value=f"{current_total:,.2f}")
            
            desired_total = st.number_input("Enter Desired Total Amount:", min_value=0.0, value=float(current_total), step=0.01, format="%.2f")
            
            # --- CALCULATION BUTTON ---
            if st.button("Find Rows to Remove"):
                desired_total_int = int(round(desired_total * 100))
                diff_int = current_total_int - desired_total_int
                
                if diff_int == 0:
                    st.success("The total is already correct!")
                    st.session_state.solution_indices = None 
                    
                elif diff_int < 0:
                    st.warning(f"The current total is LESS than the target by {abs(diff_int)/100:,.2f}. You need to ADD rows, not remove them.")
                    st.session_state.solution_indices = None 
                    
                else:
                    st.info(f"Searching for rows that sum to exactly: {diff_int/100:,.2f}...")
                    
                    candidates_df = df_clean[df_clean['Amount_Int'] <= diff_int]
                    candidates = list(zip(candidates_df.index, candidates_df['Amount_Int']))
                    
                    with st.spinner('Calculating...'):
                        result = solve_subset_sum(candidates, diff_int)
                        
                    if result:
                        st.session_state.solution_indices = result
                    else:
                        st.session_state.solution_indices = None
                        st.error("❌ No exact combination of rows found. Please check if the target amount is correct.")

            # --- DISPLAY RESULTS & DOWNLOAD ---
            if st.session_state.solution_indices:
                st.balloons()
                st.subheader("✅ Solution Found!")
                
                # 1. Identify rows involved
                result_rows = df.loc[st.session_state.solution_indices]
                remove_sum = result_rows['Amount_Clean'].sum()
                new_total = current_total - remove_sum

                # 2. Create the FINAL dataframe (The one to download)
                # We drop the indices found by the solver
                df_final = df.drop(index=st.session_state.solution_indices)
                
                # Cleanup: Remove helper columns if they exist in the original df variable
                cols_to_drop = ['Amount_Clean', 'Amount_Int']
                df_final = df_final.drop(columns=[c for c in cols_to_drop if c in df_final.columns], errors='ignore')

                # 3. Display Metrics
                col1, col2 = st.columns(2)
                col1.metric("Amount Removing", f"{remove_sum:,.2f}")
                col2.metric("New Projected Total", f"{new_total:,.2f}")
                
                st.divider()

                # 4. DOWNLOAD BUTTON (Primary Action)
                st.subheader("⬇️ Download Your Fixed File")
                csv = df_final.to_csv(index=False).encode('utf-8')
                
                st.download_button(
                    label="📥 Download Fixed File (Rows Removed)",
                    data=csv,
                    file_name="fixed_stock_list.csv",
                    mime="text/csv",
                    type="primary" # Makes the button stand out
                )
                
                st.caption("This file contains only the rows you want to KEEP.")

                # 5. VIEW REMOVED ROWS (Optional / Expandable)
                with st.expander("Show me the rows that were removed"):
                    st.write("These rows were deleted to match your target total:")
                    st.dataframe(result_rows)

# --- FOOTER ---
st.markdown("---")
st.markdown(
    """
    <div style="text-align: center; color: #808080; margin-top: 20px;">
        <small>Designed and Developed by <b>Abhijeet Rogye</b></small>
    </div>
    """,
    unsafe_allow_html=True
)
