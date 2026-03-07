    def generate_purchase_order_csv(self, forecasts: pd.DataFrame = None, 
                                     top_n: int = 50,
                                     output_path: str = None) -> str:
        """
        Tạo file CSV đơn hàng cần đặt cho tuần tới
        
        Logic ưu tiên:
        1. Đảm bảo đủ lượng tồn kho tối thiểu (Tồn nhỏ nhất)
        2. Sản phẩm bán được nhiều ưu tiên cao hơn
        3. Sản phẩm tạo nhiều doanh thu được highlight (vàng - high margin)
        
        Công thức: Lượng cần nhập = MAX(Dự báo 7 ngày, Tồn nhỏ nhất) - Tồn kho hiện tại
        
        Args:
            forecasts: DataFrame từ predict_next_week(). Nếu None sẽ chạy dự báo mới.
            top_n: Số sản phẩm cần đặt (mặc định 50)
            output_path: Đường dẫn file output. Nếu None sẽ dùng mặc định.
            
        Returns:
            Đường dẫn file CSV đã tạo
        """
        logger.info("=" * 60)
        logger.info("📦 TẠO ĐƠN HÀNG CẦN ĐẶT (Purchase Order)")
        logger.info("=" * 60)
        
        # Nếu không có forecasts thì chạy dự báo mới
        if forecasts is None or forecasts.empty:
            logger.info("Chưa có dữ liệu dự báo, đang chạy predict_next_week...")
            forecasts = self.predict_next_week(use_abc_filter=True, abc_top_n=50)
        
        if forecasts.empty:
            logger.error("❌ Không có dữ liệu dự báo để tạo đơn hàng")
            return None
        
        product_list = forecasts['ma_hang'].unique().tolist()
        products_str = "', '".join(str(p) for p in product_list)
        
        # 1. Lấy thông tin từ PostgreSQL (mã vạch, tồn nhỏ nhất)
        logger.info("📥 Đang lấy thông tin tồn kho tối thiểu từ DanhSachSanPham...")
        try:
            from sqlalchemy import text
            with self.pg.get_connection() as conn:
                product_info_query = f"""
                SELECT 
                    ma_hang,
                    ma_vach,
                    ten_hang,
                    thuong_hieu,
                    gia_von_mac_dinh,
                    gia_ban_mac_dinh,
                    COALESCE(ton_nho_nhat, 0) as ton_nho_nhat
                FROM products
                WHERE ma_hang IN ('{products_str}')
                """
                product_info_df = pd.read_sql(text(product_info_query), conn)
                product_info = {}
                for _, row in product_info_df.iterrows():
                    product_info[row['ma_hang']] = {
                        'ma_vach': row['ma_vach'] or row['ma_hang'],
                        'ten_hang': row['ten_hang'],
                        'thuong_hieu': row['thuong_hieu'],
                        'gia_von': row['gia_von_mac_dinh'] or 0,
                        'gia_ban': row['gia_ban_mac_dinh'] or 0,
                        'ton_nho_nhat': row['ton_nho_nhat'] or 0,
                        'margin': ((row['gia_ban_mac_dinh'] - row['gia_von_mac_dinh']) / row['gia_von_mac_dinh'] * 100) 
                                  if row['gia_von_mac_dinh'] and row['gia_von_mac_dinh'] > 0 else 0
                    }
                logger.info(f"✅ Loaded {len(product_info)} products from DanhSachSanPham")
        except Exception as e:
            logger.warning(f"⚠️ Không thể load từ PostgreSQL: {e}")
            product_info = {}
        
        # 2. Lấy tồn kho HIỆN TẠI từ inventory_transactions (PostgreSQL)
        logger.info("📥 Đang lấy tồn kho hiện tại...")
        try:
            from sqlalchemy import text
            with self.pg.get_connection() as conn:
                inventory_query = f"""
                SELECT DISTINCT ON (ma_hang)
                    ma_hang,
                    ton_cuoi_ky as ton_hien_tai
                FROM inventory_transactions
                WHERE ma_hang IN ('{products_str}')
                ORDER BY ma_hang, ngay_bao_cao DESC
                """
                inventory_df = pd.read_sql(text(inventory_query), conn)
                current_stock_map = dict(zip(inventory_df['ma_hang'], inventory_df['ton_hien_tai']))
                logger.info(f"✅ Loaded current stock for {len(current_stock_map)} products")
        except Exception as e:
            logger.warning(f"⚠️ Không thể load tồn kho hiện tại: {e}")
            current_stock_map = {}
        
        # 3. Lấy số lượng bán 4 tuần gần nhất từ ClickHouse (để ưu tiên)
        logger.info("📊 Đang tính số lượng bán 4 tuần gần nhất...")
        try:
            sales_query = f"""
            SELECT 
                product_code as ma_hang,
                SUM(quantity_sold) as total_sold_4weeks,
                SUM(gross_revenue) as total_revenue_4weeks
            FROM retail_dw.fct_regular_sales
            WHERE product_code IN ('{products_str}')
              AND transaction_date >= today() - 28
            GROUP BY product_code
            """
            sales_df = self.ch.query(sales_query)
            sales_map = {}
            for _, row in sales_df.iterrows():
                sales_map[row['ma_hang']] = {
                    'quantity_sold': row['total_sold_4weeks'] or 0,
                    'revenue': row['total_revenue_4weeks'] or 0
                }
            logger.info(f"✅ Loaded 4-week sales data for {len(sales_map)} products")
        except Exception as e:
            logger.warning(f"⚠️ Không thể load dữ liệu bán hàng: {e}")
            sales_map = {}
        
        # 4. Tổng hợp dự báo theo sản phẩm (7 ngày)
        product_summary = forecasts.groupby(['ma_hang', 'ten_san_pham']).agg({
            'predicted_quantity': 'sum'
        }).reset_index()
        product_summary.columns = ['ma_hang', 'ten_san_pham', 'forecast_7d']
        
        # 5. Thêm các thông tin bổ sung
        product_summary['ma_vach'] = product_summary['ma_hang'].map(
            lambda x: product_info.get(x, {}).get('ma_vach', x))
        product_summary['ten_hang_day_du'] = product_summary['ma_hang'].map(
            lambda x: product_info.get(x, {}).get('ten_hang', ''))
        product_summary['ton_nho_nhat'] = product_summary['ma_hang'].map(
            lambda x: product_info.get(x, {}).get('ton_nho_nhat', 0))
        product_summary['ton_hien_tai'] = product_summary['ma_hang'].map(
            lambda x: current_stock_map.get(x, 0))
        product_summary['da_ban_4tuan'] = product_summary['ma_hang'].map(
            lambda x: sales_map.get(x, {}).get('quantity_sold', 0))
        product_summary['doanh_thu_4tuan'] = product_summary['ma_hang'].map(
            lambda x: sales_map.get(x, {}).get('revenue', 0))
        product_summary['margin_pct'] = product_summary['ma_hang'].map(
            lambda x: product_info.get(x, {}).get('margin', 0))
        
        # 6. Tính LƯỢNG CẦN NHẬP
        # Công thức: MAX(Dự báo 7 ngày, Tồn nhỏ nhất) - Tồn kho hiện tại
        product_summary['luong_can_nhap'] = (
            product_summary[['forecast_7d', 'ton_nho_nhat']].max(axis=1) 
            - product_summary['ton_hien_tai']
        ).clip(lower=0)  # Không nhập số âm
        
        # 7. SẮP XẾP ƯU TIÊN
        # Primary: Lượng cần nhập (nhiều nhất = cần gấp nhất)
        # Secondary: Số lượng đã bán (bán nhiều = ưu tiên cao)
        # Tertiary: Doanh thu (để highlight high value)
        product_summary = product_summary.sort_values(
            ['luong_can_nhap', 'da_ban_4tuan', 'doanh_thu_4tuan'], 
            ascending=[False, False, False]
        )
        
        # 8. Lấy top N sản phẩm
        top_products = product_summary.head(top_n).copy()
        
        # Đánh dấu sản phẩm HIGH MARGIN (> 20% margin) và HIGH VALUE (top doanh thu)
        top_products['is_high_margin'] = top_products['margin_pct'] > 20
        top_products['is_high_value'] = top_products['doanh_thu_4tuan'] >= top_products['doanh_thu_4tuan'].quantile(0.8)
        
        logger.info(f"\n📊 Danh sách {len(top_products)} sản phẩm cần đặt hàng:")
        logger.info(f"   - Tổng lượng cần nhập: {top_products['luong_can_nhap'].sum():,.0f} units")
        logger.info(f"   - Sản phẩm HIGH MARGIN (>20%): {top_products['is_high_margin'].sum()}")
        logger.info(f"   - Sản phẩm HIGH VALUE (top 20%): {top_products['is_high_value'].sum()}")
        
        # 9. Tạo đơn hàng
        purchase_orders = []
        for idx, row in top_products.iterrows():
            # Xác định mức độ ưu tiên
            if row['luong_can_nhap'] > row['ton_hien_tai'] * 2:
                uu_tien = '🔴 Cần gấp'
            elif row['luong_can_nhap'] > 0:
                uu_tien = '🟡 Cần đủ'
            else:
                uu_tien = '🟢 Đủ hàng'
            
            # Ghi chú highlight
            ghi_chu = ''
            if row['is_high_margin'] and row['is_high_value']:
                ghi_chu = '⭐ HIGH MARGIN + HIGH VALUE'
            elif row['is_high_margin']:
                ghi_chu = '💰 HIGH MARGIN'
            elif row['is_high_value']:
                ghi_chu = '💎 HIGH VALUE'
            
            purchase_orders.append({
                'stt': len(purchase_orders) + 1,
                'ma_hang': row['ma_hang'],
                'ma_vach': row['ma_vach'],
                'ten_san_pham': row['ten_hang_day_du'] or row['ten_san_pham'],
                'luong_can_nhap': round(row['luong_can_nhap']),
                'ton_nho_nhat': round(row['ton_nho_nhat']),
                'ton_hien_tai': round(row['ton_hien_tai']),
                'du_bao_7ngay': round(row['forecast_7d']),
                'da_ban_4tuan': round(row['da_ban_4tuan']),
                'doanh_thu_4tuan': round(row['doanh_thu_4tuan']),
                'margin_pct': round(row['margin_pct'], 1),
                'uu_tien': uu_tien,
                'ghi_chu': ghi_chu
            })
        
        # 10. Tạo DataFrame và lưu file
        po_df = pd.DataFrame(purchase_orders)
        po_df['stt'] = range(1, len(po_df) + 1)
        
        if output_path is None:
            output_dir = '/app/output' if os.path.exists('/app/output') else os.getcwd()
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = os.path.join(output_dir, f'purchase_order_{timestamp}.csv')
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        po_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        
        logger.info(f"\n✅ Đã tạo file đơn hàng: {output_path}")
        logger.info(f"   - Tổng lượng đặt: {po_df['luong_can_nhap'].sum():,.0f} units")
        
        # Hiển thị top 15
        logger.info("\n🔥 Top 15 sản phẩm ưu tiên đặt hàng:")
        logger.info(f"{'STT':<4} {'Mã hàng':<12} {'Tên sản phẩm':<30} {'Cần nhập':<10} {'Tồn hiện tại':<12} {'Ưu tiên':<15} {'Ghi chú'}")
        logger.info("-" * 130)
        for _, row in po_df.head(15).iterrows():
            name_short = row['ten_san_pham'][:28] if len(str(row['ten_san_pham'])) > 28 else row['ten_san_pham']
            logger.info(f"{row['stt']:<4} {row['ma_hang']:<12} {name_short:<30} "
                       f"{row['luong_can_nhap']:>8,} {row['ton_hien_tai']:>10,} "
                       f"{row['uu_tien']:<15} {row['ghi_chu']}")
        
        return output_path
