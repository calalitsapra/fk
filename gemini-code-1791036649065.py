import streamlit as st
import pandas as pd
import os
import io

# Define the local master file
MASTER_FILE = 'master_sku.csv'

# Initialize the master file if it doesn't exist
if not os.path.exists(MASTER_FILE):
    pd.DataFrame(columns=['SKU', 'Product', 'Cost_Price']).to_csv(MASTER_FILE, index=False)

st.set_page_config(page_title="Flipkart Profitability Analyzer", layout="wide")
st.title("📦 Product Profitability Analyzer")

# Create tabs for the app interface
tab1, tab2 = st.tabs(["📊 Generate Report", "⚙️ Manage Master Data (SKUs & Costs)"])

# --- TAB 2: MASTER DATA MANAGEMENT ---
with tab2:
    st.header("Master SKU & Cost Database")
    st.write("Add new SKUs, map them to a Product, and update Cost Prices below. Press Save when done.")
    
    # Load current master data
    master_df = pd.read_csv(MASTER_FILE)
    
    # Render an editable dataframe so you can add/edit rows directly in the browser
    edited_df = st.data_editor(master_df, num_rows="dynamic", use_container_width=True)
    
    if st.button("💾 Save Master Data", type="primary"):
        edited_df.to_csv(MASTER_FILE, index=False)
        st.success("Master data updated successfully!")

# --- TAB 1: REPORT GENERATION ---
with tab1:
    st.header("Upload Monthly Sheet")
    uploaded_file = st.file_uploader("Upload your Flipkart Monthly Excel/CSV Sheet", type=['xlsx', 'csv'])
    
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('csv'):
                input_df = pd.read_csv(uploaded_file)
            else:
                input_df = pd.read_excel(uploaded_file)
            
            st.write("Preview of Uploaded Data:")
            st.dataframe(input_df.head(3))
            
            st.markdown("### Map Your Columns")
            col1, col2, col3 = st.columns(3)
            with col1:
                sku_col = st.selectbox("Which column has the Seller SKU?", input_df.columns)
            with col2:
                revenue_col = st.selectbox("Which column has the Settlement/Sales Amount?", input_df.columns)
            with col3:
                qty_col = st.selectbox("Which column has the Quantity?", input_df.columns)
            
            if st.button("🚀 Generate Product-Wise Report"):
                # Load the latest master data
                current_master = pd.read_csv(MASTER_FILE)
                
                # Merge the input sheet with the master sheet based on SKU
                merged_df = pd.merge(input_df, current_master, left_on=sku_col, right_on='SKU', how='left')
                
                # Check for unmapped SKUs
                unmapped_skus = merged_df[merged_df['Product'].isna()][sku_col].dropna().unique()
                if len(unmapped_skus) > 0:
                    st.error(f"⚠️ Found {len(unmapped_skus)} SKUs in your upload that are missing from your Master Data!")
                    st.write(unmapped_skus)
                    st.info("Please go to the 'Manage Master Data' tab, add these SKUs, save, and try again.")
                else:
                    # Perform Profitability Calculations
                    merged_df['Total_Cost'] = merged_df[qty_col] * merged_df['Cost_Price']
                    merged_df['Profitability'] = merged_df[revenue_col] - merged_df['Total_Cost']
                    
                    # Pivot the table by 'Product'
                    report = merged_df.groupby('Product').agg({
                        qty_col: 'sum',
                        revenue_col: 'sum',
                        'Total_Cost': 'sum',
                        'Profitability': 'sum'
                    }).reset_index()
                    
                    # Rename columns for cleanliness
                    report.rename(columns={
                        qty_col: 'Total Quantity Sold', 
                        revenue_col: 'Total Settlement Amount'
                    }, inplace=True)
                    
                    st.success("✅ Report Generated Successfully!")
                    st.dataframe(report, use_container_width=True)
                    
                    # Create an Excel file in memory for download
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        report.to_excel(writer, index=False, sheet_name='Profitability')
                    processed_data = output.getvalue()
                    
                    st.download_button(
                        label="📥 Download Final Profitability Report (Excel)",
                        data=processed_data,
                        file_name="Product_Wise_Profitability.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
        except Exception as e:
            st.error(f"An error occurred while processing the file: {e}")