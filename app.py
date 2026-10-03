import streamlit as st
import pandas as pd
import os
import io
import plotly.express as px

# ==========================================
# ⚙️ CONFIGURATION: EXCEL COLUMN LETTERS
# ==========================================
COL_SKU = "A"
COL_NET_UNITS = "H"
COL_CUSTOMER_RETURN = "F" 
COL_BANK_SETTLEMENT = "AT"
# ==========================================

MASTER_FILE = 'master_sku.csv'

if not os.path.exists(MASTER_FILE):
    pd.DataFrame(columns=['SKU', 'Product', 'Category', 'Cost_Price']).to_csv(MASTER_FILE, index=False)

def letter_to_index(letter):
    letter = letter.upper()
    result = 0
    for char in letter:
        result = result * 26 + (ord(char) - ord('A') + 1)
    return result - 1

st.set_page_config(page_title="Flipkart Profitability Analyzer", layout="wide")
st.title("📦 Product Profitability Analyzer")

tab1, tab2 = st.tabs(["📊 Generate Report", "⚙️ Manage Master Data"])

# --- TAB 2: MASTER DATA MANAGEMENT ---
with tab2:
    st.header("1. Bulk Upload Master Data")
    st.write("Upload an Excel/CSV file containing your master SKUs. Ensure it has columns named exactly: **SKU**, **Product**, **Category**, and **Cost_Price**.")
    
    master_upload = st.file_uploader("Upload Master Sheet", type=['xlsx', 'csv'], key="master_uploader")
    
    if master_upload is not None:
        try:
            if master_upload.name.endswith('csv'):
                new_master = pd.read_csv(master_upload)
            else:
                new_master = pd.read_excel(master_upload)
            new_master.to_csv(MASTER_FILE, index=False)
            st.success("✅ Master Database updated successfully from your file!")
        except Exception as e:
            st.error(f"Error processing master upload: {e}")
            
    st.header("2. View & Edit Master Database")
    master_df = pd.read_csv(MASTER_FILE)
    edited_df = st.data_editor(master_df, num_rows="dynamic", use_container_width=True)
    
    if st.button("💾 Save Manual Edits", type="primary"):
        edited_df.to_csv(MASTER_FILE, index=False)
        st.success("Manual edits saved successfully!")

# --- TAB 1: REPORT GENERATION ---
with tab1:
    st.header("Upload Monthly Sheet")
    uploaded_file = st.file_uploader("Upload your Flipkart Monthly Excel/CSV Sheet", type=['xlsx', 'csv'], key="monthly_uploader")
    
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('csv'):
                raw_df = pd.read_csv(uploaded_file, header=None, low_memory=False)
            else:
                try:
                    raw_df = pd.read_excel(uploaded_file, sheet_name='SKU-level P&L', header=None)
                except ValueError:
                    raw_df = pd.read_excel(uploaded_file, sheet_name=1, header=None)
            
            idx_sku = letter_to_index(COL_SKU)
            idx_units = letter_to_index(COL_NET_UNITS)
            idx_return = letter_to_index(COL_CUSTOMER_RETURN)
            idx_settlement = letter_to_index(COL_BANK_SETTLEMENT)
            
            input_df = raw_df.iloc[:, [idx_sku, idx_units, idx_return, idx_settlement]].copy()
            input_df.columns = ['SKU', 'Net_Units', 'Customer_Returns', 'Bank_Settlement']
            
            input_df = input_df.dropna(subset=['SKU'])
            input_df = input_df[~input_df['SKU'].astype(str).str.contains("SKU ID|None|nan", case=False, na=False)]
            
            for col in ['Net_Units', 'Customer_Returns', 'Bank_Settlement']:
                input_df[col] = pd.to_numeric(input_df[col], errors='coerce').fillna(0)
            
            if st.button("🚀 Generate Product-Wise Report"):
                current_master = pd.read_csv(MASTER_FILE)
                merged_df = pd.merge(input_df, current_master, on='SKU', how='left')
                
                unmapped_skus = merged_df[merged_df['Product'].isna()]['SKU'].dropna().unique()
                
                if len(unmapped_skus) > 0:
                    st.error(f"⚠️ Found {len(unmapped_skus)} SKUs in your upload that are missing from your Master Data!")
                    st.dataframe(pd.DataFrame(unmapped_skus, columns=["Missing SKUs"]))
                    st.info("Go to the Master Data tab, add these SKUs, assign their Product, Category & Cost Price, save, and try again.")
                else:
                    merged_df['Cost_Price'] = pd.to_numeric(merged_df['Cost_Price'], errors='coerce').fillna(0)
                    merged_df['Total_Cost'] = merged_df['Net_Units'] * merged_df['Cost_Price']
                    merged_df['Profit'] = merged_df['Bank_Settlement'] - merged_df['Total_Cost']
                    
                    report = merged_df.groupby('Product').agg({
                        'Profit': 'sum',
                        'Total_Cost': 'sum',
                        'Bank_Settlement': 'sum',
                        'Net_Units': 'sum',
                        'Customer_Returns': 'sum'
                    }).reset_index()
                    
                    report.rename(columns={
                        'Product': 'Row Labels',
                        'Profit': 'Sum of Profit',
                        'Total_Cost': 'Sum of Total Cost',
                        'Bank_Settlement': 'Sum of Bank Settlement',
                        'Net_Units': 'Sum of Net Units',
                        'Customer_Returns': 'Sum of Customer Returns'
                    }, inplace=True)
                    
                    # ---------------------------------------------------------
                    # MAIN REPORT FORMATTING
                    # ---------------------------------------------------------
                    report.sort_values(by='Sum of Profit', ascending=True, inplace=True)
                    
                    numeric_cols = ['Sum of Profit', 'Sum of Total Cost', 'Sum of Bank Settlement', 'Sum of Net Units', 'Sum of Customer Returns']
                    report[numeric_cols] = report[numeric_cols].round(0).astype(int)
                    
                    totals = report[numeric_cols].sum()
                    total_row = pd.DataFrame([['TOTAL'] + totals.tolist()], columns=['Row Labels'] + numeric_cols)
                    report = pd.concat([total_row, report], ignore_index=True)
                    
                    report['Profit Per Unit'] = report.apply(
                        lambda row: int(round(row['Sum of Profit'] / row['Sum of Net Units'], 0)) if row['Sum of Net Units'] > 0 else 0,
                        axis=1
                    )
                    
                    report['Return %'] = report.apply(
                        lambda row: f"{(row['Sum of Customer Returns'] / row['Sum of Net Units'] * 100):.1f}%" if row['Sum of Net Units'] > 0 else "0.0%", 
                        axis=1
                    )
                    
                    # ---------------------------------------------------------
                    # NEW SIDE TABLE: Return % in Decreasing Order
                    # ---------------------------------------------------------
                    side_table = report.iloc[1:].copy()
                    
                    side_table['Raw_Return'] = side_table.apply(
                        lambda row: (row['Sum of Customer Returns'] / row['Sum of Net Units'] * 100) if row['Sum of Net Units'] > 0 else 0.0, 
                        axis=1
                    )
                    
                    side_table = side_table.sort_values(by='Raw_Return', ascending=False)
                    side_table.rename(columns={'Row Labels': 'Product'}, inplace=True)
                    side_table = side_table[['Product', 'Return %']].reset_index(drop=True)
                    side_table.index = side_table.index + 1  
                    side_table.index.name = "S.No"
                    
                    # ---------------------------------------------------------
                    # CSS STYLING
                    # ---------------------------------------------------------
                    def apply_styles(row):
                        styles = [''] * len(row)
                        if row.name == 0:
                            styles = ['font-weight: bold'] * len(row)
                        
                        for col in ['Sum of Profit', 'Sum of Bank Settlement', 'Profit Per Unit']:
                            if col in row.index:
                                val = row[col]
                                if isinstance(val, (int, float)) and val < 0:
                                    col_idx = row.index.get_loc(col)
                                    styles[col_idx] = styles[col_idx] + '; color: red; font-weight: bold'
                        return styles
                        
                    styled_report = report.style.apply(apply_styles, axis=1)
                    
                    st.success("✅ Report Generated Successfully!")
                    
                    # ---------------------------------------------------------
                    # LAYOUT: Side-by-Side Columns
                    # ---------------------------------------------------------
                    col1, col2 = st.columns([2.5, 1])
                    
                    with col1:
                        st.dataframe(styled_report, use_container_width=False)
                        
                        output = io.BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            styled_report.to_excel(writer, index=False, sheet_name='Profitability')
                        
                        st.download_button(
                            label="📥 Download Final Profitability Report (Excel)",
                            data=output.getvalue(),
                            file_name="Product_Wise_Profitability.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                        
                    with col2:
                        st.markdown("**High Returns Analysis**")
                        st.dataframe(side_table, use_container_width=True)

                    # ---------------------------------------------------------
                    # CATEGORY PIE CHARTS (With Values in Thousands)
                    # ---------------------------------------------------------
                    if 'Category' in merged_df.columns:
                        st.markdown("---")
                        st.header("📊 Category Performance")
                        
                        cat_df = merged_df.groupby('Category').agg({
                            'Bank_Settlement': 'sum',
                            'Profit': 'sum'
                        }).reset_index()
                        
                        # Convert absolute values to thousands
                        cat_df['Sales_in_k'] = cat_df['Bank_Settlement'] / 1000
                        cat_df['Profit_in_k'] = cat_df['Profit'] / 1000
                        
                        chart_col1, chart_col2 = st.columns(2)
                        
                        with chart_col1:
                            fig_sales = px.pie(
                                cat_df, 
                                values='Sales_in_k', 
                                names='Category', 
                                title="Category-Wise Sales (in '000s)",
                                hole=0.3
                            )
                            # Custom template: shows value to 2 decimal places and the percentage
                            fig_sales.update_traces(texttemplate="%{value:.2f}<br>(%{percent})")
                            st.plotly_chart(fig_sales, use_container_width=True)
                            
                        with chart_col2:
                            cat_df_profit = cat_df[cat_df['Profit_in_k'] > 0]
                            fig_profit = px.pie(
                                cat_df_profit, 
                                values='Profit_in_k', 
                                names='Category', 
                                title="Category-Wise Profit (in '000s)",
                                hole=0.3
                            )
                            # Custom template: shows value to 2 decimal places and the percentage
                            fig_profit.update_traces(texttemplate="%{value:.2f}<br>(%{percent})")
                            st.plotly_chart(fig_profit, use_container_width=True)
                            
                            # Safely draw the caption directly in the website layout below the chart
                            st.caption("*Categories with net losses are excluded from this chart.")
                        
        except Exception as e:
            st.error(f"An error occurred while processing the file: {e}")