# ML Pipeline Explanation - Tài liệu cho Data Scientist

## Tổng quan hệ thống ML

Hệ thống sử dụng **2 models** với mục đích bổ trợ lẫn nhau:

| Model | Level | Mục đích | Độ tin cậy |
|-------|-------|----------|------------|
| **Model 1** | Product-level (SKU) | Dự báo chi tiết từng sản phẩm | HIGH |
| **Model 2** | Category-level | Dự báo xu hướng ngành hàng | MEDIUM |

---

## Model 1: Product-Level Forecasting

### Architecture

```
Input: Historical sales data (fct_regular_sales)
↓
Feature Engineering (20+ features)
↓
XGBoost Regressor → Predicted quantity
↓
Post-processing (clip negative, round)
↓
Output: 7-day forecast per product
```

### Feature Categories

#### 1. Time-Based Features (Calendar)
| Feature | Ý nghĩa | Tuning impact |
|---------|---------|---------------|
| `day_of_week` | Thứ trong tuần (1-7) | Capture weekly seasonality |
| `day_of_month` | Ngày trong tháng (1-31) | Detect payday effects |
| `month` | Tháng (1-12) | Yearly seasonality |
| `is_weekend` | Cuối tuần flag | Weekend shopping patterns |
| `is_month_start/end` | Đầu/cuối tháng | Salary-driven purchases |
| `is_holiday` | Ngày lỉ | Holiday spikes |

**Tinh chỉnh**: Thêm/bớt holidays sẽ ảnh hưởng đến dự báo ngày đặc biệt.

#### 2. Lag Features (Historical values)
| Feature | Mô tả | Minimum Data Required |
|---------|-------|----------------------|
| `lag_1_quantity` | Số lượng bán hôm qua | 2 days |
| `lag_7_quantity` | Số lượng bán cách đây 1 tuần | 8 days |
| `lag_14_quantity` | Số lượng bán cách đây 2 tuần | 15 days |
| `lag_30_quantity` | Số lượng bán cách đây 1 tháng | 31 days |

**Adaptive behavior**: 
- Nếu dữ liệu < 30 ngày, tự động bỏ lag 30
- Nếu dữ liệu < 15 ngày, tự động bỏ lag 14
- Nếu dữ liệu < 8 ngày, tự động bỏ lag 7
- Nếu dữ liệu < 2 ngày, training sẽ fail (không đủ cho lag_1)

**Data Requirements for Training**:
```
Minimum: 2 days (chỉ có lag_1)
Recommended: 31+ days (đầy đủ lag_1, lag_7, lag_14, lag_30)
Optimal: 90+ days (lag features + rolling statistics ổn định)
```

**How lag features are created**:
```python
# Sử dụng pandas shift() theo nhóm (chi_nhanh, ma_hang)
df[f'lag_{lag}_quantity'] = df.groupby(['chi_nhanh', 'ma_hang'])['daily_quantity'].shift(lag)
```

**Tinh chỉnh**: 
- Thêm lag 3 ngày → capture short-term trends
- Bỏ lag 30 → khi dữ liệu ngắn, tránh overfitting
- **Cold start handling**: Sản phẩm < 2 ngày dữ liệu sẽ dùng category median thay vì model prediction

#### 3. Rolling Statistics
| Feature | Window | Ý nghĩa |
|---------|--------|---------|
| `rolling_mean_7` | 7 ngày | Trend ngắn hạn |
| `rolling_mean_14` | 14 ngày | Trend trung hạn |
| `rolling_mean_30` | 30 ngày | Trend dài hạn |
| `rolling_std_7/14/30` | 7/14/30 ngày | Độ biến động (volatility) |

**Tinh chỉnh**: 
- Window ngắn → phản ứng nhanh với thay đổi, nhạy noise
- Window dài → ổn định nhưng chậm phản ứng

#### 4. Dynamic Seasonal Factors ⭐
| Feature | Nguồn | Ý nghĩa |
|---------|-------|---------|
| `seasonal_factor` | Tính từ lịch sử | Tỷ lệ tăng trưởng mùa vụ |
| `is_peak_day` | 0/1 | Có phải ngày cao điểm không |
| `quantity_factor` | Tính từ lịch sử | Tỷ lệ tăng quantity |

**Cách tính**: 
```
seasonal_factor = (Doanh số ngày đặc biệt) / (Doanh số ngày thường trung bình)

Ví dụ: Black Friday có doanh số cao hơn 42% → seasonal_factor = 1.42
```

**Tinh chỉnh**:
- Tăng window tính toán (từ 1 năm lên 2 năm) → ổn định hơn
- Giảm window → phản ứng nhanh với xu hướng mới

#### 5. Categorical Encoding
| Feature | Nguồn |
|---------|-------|
| `branch_encoded` | Mã hóa chi nhánh |
| `category1_encoded` | Mã hóa nhóm hàng cấp 1 |
| `category2_encoded` | Mã hóa nhóm hàng cấp 2 |
| `brand_encoded` | Mã hóa thương hiệu |
| `abc_encoded` | Mã hóa ABC class |

**Ý nghĩa**: Cho phép model học pattern riêng của từng nhóm.

---

## Metrics & Evaluation

### Model 1: MdAPE (Median Absolute Percentage Error)

```
MdAPE = median(|(actual - predicted) / actual|) × 100
```

**Tại sao dùng MdAPE thay MAPE?**
- MdAPE ít nhạy với outliers hơn MAPE
- Phù hợp khi có sản phẩm bán rất ít (gần 0)

**Interpretation**:
| MdAPE | Đánh giá |
|-------|----------|
| < 10% | Rất tốt |
| 10-20% | Tốt |
| 20-30% | Chấp nhận được |
| > 30% | Cần cải thiện |

### Model 2: MAPE (Mean Absolute Percentage Error)

```
MAPE = mean(|(actual - predicted) / actual|) × 100
```

**Lý do**: Category-level ít outliers hơn product-level.

---

## Hyperparameter Tuning

### XGBoost Parameters

| Parameter | Default | Range | Impact |
|-----------|---------|-------|--------|
| `n_estimators` | 500 | 100-1000 | Số cây. Cao → overfitting risk |
| `max_depth` | 6 | 3-10 | Độ sâu cây. Cao → capture complex patterns |
| `learning_rate` | 0.1 | 0.01-0.3 | Tốc độ học. Thấp → cần nhiều cây hơn |
| `subsample` | 0.8 | 0.6-1.0 | % data mỗi cây. Giảm → giảm overfitting |
| `colsample_bytree` | 0.8 | 0.6-1.0 | % features mỗi cây |
| `reg_alpha` | 0 | 0-10 | L1 regularization. Tăng → sparse model |
| `reg_lambda` | 1 | 0-10 | L2 regularization. Tăng → smooth weights |

### Optuna Tuning Strategy

```
Search space:
- max_depth: [3, 10]
- learning_rate: [0.01, 0.3] (log scale)
- subsample: [0.6, 1.0]
- colsample_bytree: [0.6, 1.0]
- reg_alpha: [1e-8, 10] (log scale)
- reg_lambda: [1e-8, 10] (log scale)

Objective: Minimize MdAPE (Model 1) or MAPE (Model 2)
```

**Tinh chỉnh số trials**:
- 10-20 trials: Quick test
- 50 trials: Balanced (default)
- 100+ trials: Optimal but slow

---

## Model Comparison (Consistency Analysis)

### Consistency Score

```
Consistency Score = % categories có |Model1 - Model2| < 10%
```

**Interpretation**:
| Score | Ý nghĩa |
|-------|---------|
| > 80% | 2 models đồng thuận cao |
| 60-80% | Có sự khác biệt cần review |
| < 60% | Có vấn đề với data hoặc model |

**Khi nào chênh lệch đáng lo?**
- Model 2 cao hơn nhiều → Có thể Model 1 đang underpredict
- Model 1 cao hơn nhiều → Có thể Model 1 overpredict

---

## Feature Importance Analysis

### Cách interpret

```python
# XGBoost built-in importance
importance = model.feature_importances_
```

**Các loại importance**:
1. **Gain**: Improvement in accuracy brought by a feature
2. **Cover**: Relative quantity of observations concerned by a feature
3. **Frequency**: Relative number of times a feature appears in trees

**Thông thường features quan trọng nhất**:
1. `lag_1_quantity` (autoregressive)
2. `seasonal_factor` (nếu có mùa vụ rõ)
3. `rolling_mean_7` (trend ngắn hạn)
4. `day_of_week` (weekly pattern)

---

## Data Validation & Quality Checks

### 1. Sales Data Validation

**Kiểm tra dữ liệu bán hàng thực tế:**

```python
# Chỉ giữ records có dữ liệu bán thực tế
df = df[df['daily_quantity'] > 0]
df = df[df['daily_revenue'] > 0]
```

**Tại sao cần validation:**
- Loại bỏ placeholder records (quantity = 0 hoặc NULL)
- Đảm bảo model học từ giao dịch thực, không phải records trống
- Tránh dự báo = 0 do thiếu dữ liệu

**Log output:**
```
⚠️  Đã loại bỏ 850 records (5.2%) do không có dữ liệu bán hàng
✅ Đã load 15,420 records bán hàng thực tế
   📊 Total quantity: 2,450,800
   📊 Total revenue: 3,245,600,000
```

### 2. Time-Series Continuity Checks

**Kiểm tra tính liên tục theo ngày:**

| Check | Mô tả | Ngưỡng cảnh báo |
|-------|-------|-----------------|
| **Date gaps** | Ngày bị thiếu dữ liệu | > 0 ngày missing |
| **Min days** | Số ngày tối thiểu | < 14 ngày 🔴 |
| **Distribution** | Phân phối đều/ngày | < 50% average 🟡 |

**Log output:**
```
📊 Date range: 2024-01-01 to 2024-02-29
📊 Expected days: 60, Actual days with data: 58
⚠️  Missing data for 2 days: [2024-02-15, 2024-02-16]

📊 Daily data distribution:
   - Min records/day: 150
   - Max records/day: 320
   - Avg records/day: 235.5
   ✅ Good daily data distribution
```

**Các mức cảnh báo:**

| Tình huống | Mức độ | Khuyến nghị |
|------------|--------|-------------|
| < 14 ngày | 🔴 Nghiêm trọng | Thu thập thêm dữ liệu |
| 14-30 ngày | 🟡 Cảnh báo | Dự báo ngắn hạn only |
| Có ngày = 0 records | 🔴 Nghiêm trọng | Kiểm tra ETL pipeline |
| Phân phối không đều | 🟡 Cảnh báo | Review data collection |

### 3. Lag Feature Validation

**Kiểm tra sau khi tạo features:**

```python
# Training log sẽ hiển thị:
📊 Available lag features: [1, 7, 14, 30]  # hoặc ít hơn tùy data
📊 Lag features created: ['lag_1_quantity', 'lag_7_quantity', ...]
   - lag_1_quantity: 15,420 non-zero values (94.5%)
   - lag_7_quantity: 14,890 non-zero values (91.2%)
   - lag_14_quantity: 13,250 non-zero values (81.1%)
   - lag_30_quantity: 10,150 non-zero values (62.1%)
```

**Tại sao có non-zero < 100%?**
- Những ngày đầu tiên của mỗi sản phẩm không có lag (shift tạo NA → fill 0)
- Sản phẩm mới có ít lịch sử → lag features = 0

**Cảnh báo quan trọng:**

| Tình huống | Log message | Ý nghĩa |
|------------|-------------|---------|
| Lag 30 không khả dụng | `⚠️ Chỉ có X ngày dữ liệu - lag_30 sẽ không khả dụng` | Dữ liệu < 31 ngày |
| Lag 14 không khả dụng | `⚠️ Chỉ có X ngày dữ liệu - lag_14 sẽ không khả dụng` | Dữ liệu < 15 ngày |
| Lag 7 không khả dụng | `⚠️ Chỉ có X ngày dữ liệu - lag_7 sẽ không khả dụng` | Dữ liệu < 8 ngày |
| Không đủ data | `❌ Chỉ có X ngày dữ liệu - Không đủ cho lag_1!` | Training fail |

**Best practice cho lag features:**
- **Minimum**: 14 ngày (lag_1, lag_7, lag_14)
- **Recommended**: 31+ ngày (đầy đủ 4 lag features)
- **Optimal**: 90+ ngày (lag ổn định + seasonal patterns)

### 4. Cold Start Handling

**Vấn đề:** Sản phẩm mới hoặc ít dữ liệu (< 2 ngày)

**Giải pháp:**
```python
if len(product_history) < 2:
    # Dùng category median làm fallback
    predicted_qty = category_median * seasonal_factor / 7
```

**Công thức tính category median:**
```
category_median = median(daily_quantity của tất cả sản phẩm cùng category)
```

**Tracking:**
- Số lượng cold start products được log
- Email report có section cảnh báo riêng
- Data quality metrics tracking

---

## Data Quality Indicators

### Warning signs

| Issue | Dấu hiệu | Cách xử lý |
|-------|----------|------------|
| **Cold start** | < 2 ngày data | Dùng category median fallback |
| **Missing dates** | Expected > Actual days | Kiểm tra ETL pipeline |
| **Zero records/day** | Min records/day = 0 | Check data source |
| **Outliers** | MdAPE > 50% | Winsorization hoặc review |
| **Seasonality shift** | Model 2 >> Model 1 | Review seasonal_factor |
| **Stock out** | 0 sales liên tục | Không dự báo = 0 |

---

## Best Practices

### 1. Retraining Frequency
- **Daily**: Nếu data mới mỗi ngày
- **Weekly**: Nếu ổn định (current setup)
- **Monthly**: Nếu ít biến động

### 2. Validation Strategy
- Luôn dùng TimeSeriesSplit (không dùng random)
- Minimum 3 folds
- Walk-forward validation cho production

### 3. Feature Engineering Tips
- Log transform cho highly skewed data
- Interaction terms: `is_weekend × is_holiday`
- Lag features: Thử nhiều lag khác nhau

### 4. Handling New Products (Cold Start)

**Cold start problem:** Sản phẩm có < 2 ngày dữ liệu lịch sử

**Phân loại theo mức độ dữ liệu:**

| Mức độ | Ngày dữ liệu | Phương pháp | Độ tin cậy |
|--------|--------------|-------------|------------|
| **Cold start** | < 2 ngày | Category median + seasonal | LOW |
| **Warm up** | 2-14 ngày | Model với limited features | MEDIUM |
| **Stable** | 14-30 ngày | Full model features | HIGH |
| **Mature** | > 30 ngày | Full model + all lags | HIGH |

**Công thức cold start fallback:**
```python
# Tính category median từ dữ liệu lịch sử
category_median = df.groupby('category')['daily_quantity'].median()

# Áp dụng seasonal adjustment
predicted_qty = category_median * seasonal_factor / 7
```

**Email alerts:**
- Cold start count được báo cáo trong training report
- Cảnh báo nếu > 20% products là cold start
- Recommend thu thập thêm dữ liệu nếu cần

---

## Advanced Tuning

### Custom Loss Function

Nếu underpredict nguy hiểm hơn overpredict:

```python
# Pseudo-code cho asymmetric loss
def custom_loss(y_true, y_pred):
    error = y_pred - y_true
    return np.where(error < 0,  # Underpredict
                    error ** 2 * 2.0,  # Penalty cao hơn
                    error ** 2)         # Penalty bình thường
```

### Ensemble Methods

```
Final_prediction = 0.7 × Model1 + 0.3 × Model2
```

Hoặc weighted by confidence score.

---

## Monitoring & Alerting

### Key Metrics to Track

1. **Prediction Drift**: MAPE tăng đột ngột
2. **Feature Drift**: Distribution của features thay đổi
3. **Data Freshness**: Last update timestamp
4. **Coverage**: % products có dự báo
5. **Data Quality**: Cold start %, missing dates, zero predictions

### Alert Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| MdAPE | > 25% | > 35% |
| Missing forecasts | > 5% | > 15% |
| Data latency | > 2 days | > 5 days |
| Cold start products | > 10% | > 20% |
| Missing dates | > 1 day | > 3 days |
| Zero predictions | > 0 | > 5% |

### Email Alert Colors

Training report hiển thị data quality alerts với màu sắc:

🔴 **Error (Đỏ):**
- > 20% cold start products
- Có dự báo = 0
- Data > 2 ngày không cập nhật

🟠 **Warning (Cam):**
- 5-20% cold start products
- 5-20% missing data
- Data chậm 1-2 ngày

🔵 **Info (Xanh):**
- Các trường hợp khác

**Nội dung email alert:**
```
🔴 Cảnh báo chất lượng dữ liệu
• ⚠️ 15 sản phẩm dùng category median fallback
• 🚨 3 dự báo = 0 - Cần kiểm tra ngay

💡 Khuyến nghị: Kiểm tra data pipeline và đảm bảo dữ liệu 
được cập nhật đầy đủ. Nếu tỷ lệ cold start cao, cân nhắc 
thu thập thêm dữ liệu lịch sử.
```

---

## Troubleshooting Guide

### Vấn đề: Dự báo = 0 cho tất cả sản phẩm

**Nguyên nhân có thể:**
1. **Thiếu dữ liệu bán hàng** - Kiểm tra log:
   ```
   ❌ Không có dữ liệu bán hàng hợp lệ sau khi lọc!
   ```
   
2. **Tất cả products đều là cold start** - Kiểm tra:
   ```
   ⚠️  Cold start: 100% sản phẩm dùng category median fallback
   ```

**Cách xử lý:**
- Kiểm tra bảng `fct_regular_sales` có dữ liệu không
- Verify ETL pipeline chạy thành công
- Check date range của dữ liệu

### Vấn đề: Thiếu nhiều ngày dữ liệu

**Kiểm tra:**
```
📊 Expected days: 60, Actual days with data: 45
⚠️  Missing data for 15 days
```

**Nguyên nhân:**
- ETL job failed trong các ngày đó
- Data source không có dữ liệu
- Lỗi khi import CSV

**Cách xử lý:**
- Re-run ETL cho các ngày bị thiếu
- Check Airflow DAG logs
- Verify CSV files có đầy đủ dữ liệu

### Vấn đề: MdAPE cao (> 50%)

**Nguyên nhân:**
- Outliers trong dữ liệu
- Seasonality chưa được capture
- Model underfit

**Cách xử lý:**
1. Kiểm tra winsorization đã áp dụng chưa
2. Review seasonal factors có chính xác không
3. Tăng số trials cho hyperparameter tuning
4. Thử thêm features mới

### Vấn đề: Cold start products > 20%

**Kiểm tra:**
```
⚠️  Cold start: 150 sản phẩm (25%) dùng category median fallback
```

**Nguyên nhân:**
- Nhiều sản phẩm mới
- Dữ liệu lịch sử bị xóa
- Ngưỡng "< 2 ngày" quá cao

**Cách xử lý:**
- Điều chỉnh ngưỡng cold start xuống 1 ngày
- Thu thập thêm dữ liệu lịch sử
- Dùng category-level dự báo thay vì product-level

---

## Current ML Workflow (End-to-End)

### 1. Data Loading & Validation

```
┌─────────────────────────────────────────────────────────┐
│  Bước 1: Load dữ liệu từ fct_regular_sales              │
│  ├── Query: SELECT * FROM fct_regular_sales             │
│  ├── JOIN dim_product cho category, brand, abc_class    │
│  └── JOIN int_dynamic_seasonal_factor cho factors       │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│  Bước 2: Data Validation                                │
│  ├── Loại bỏ records có quantity <= 0                   │
│  ├── Loại bỏ records có revenue <= 0                    │
│  └── Check: date range, unique days, continuity         │
└─────────────────────────────────────────────────────────┘
```

**Validation Output:**
```
✅ Loaded 150,420 rows
   📊 Total quantity: 2,450,800
   📊 Unique products: 1,250
   📊 Date range: 2024-01-01 to 2024-03-15
   📊 Unique days in data: 75
   📊 Available lag features: [1, 7, 14, 30]
   ✅ Time-series continuity: Good (75/75 days)
```

### 2. Feature Engineering

```
┌─────────────────────────────────────────────────────────┐
│  Bước 3: Tạo Features                                   │
│  ├── Time-based: day_of_week, month, is_weekend...      │
│  ├── Lag features (adaptive):                           │
│  │   ├── lag_1_quantity (nếu n_days >= 2)               │
│  │   ├── lag_7_quantity (nếu n_days >= 8)               │
│  │   ├── lag_14_quantity (nếu n_days >= 15)             │
│  │   └── lag_30_quantity (nếu n_days >= 31)             │
│  ├── Rolling statistics: mean/std 7, 14, 30 days        │
│  ├── Seasonal factors: is_peak_day, seasonal_factor     │
│  └── Encoding: branch, category, brand (categorical)    │
└─────────────────────────────────────────────────────────┘
```

**Feature Stats:**
```
✅ Created 25 features
   📊 Lag features: ['lag_1_quantity', 'lag_7_quantity', ...]
      - lag_1_quantity: 142,380 non-zero (94.6%)
      - lag_7_quantity: 138,950 non-zero (92.3%)
      - lag_14_quantity: 132,500 non-zero (88.0%)
      - lag_30_quantity: 115,200 non-zero (76.5%)
```

### 3. Model Training (2 Models)

```
┌─────────────────────────────────────────────────────────┐
│  Model 1: Product-Level Quantity Forecast               │
│  ├── Target: daily_quantity                             │
│  ├── Metric: MdAPE (Median Absolute Percentage Error)   │
│  ├── Features: Tất cả (lag, rolling, seasonal...)       │
│  └── Tuning: Optuna (default 50 trials)                 │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│  Model 2: Category-Level Trend Forecast                 │
│  ├── Target: category_daily_quantity                    │
│  ├── Metric: MAPE (Mean Absolute Percentage Error)      │
│  ├── Aggregation: Group by category, date               │
│  └── Tuning: Optuna                                     │
└─────────────────────────────────────────────────────────┘
```

**Training Output:**
```
📦 Model 1: Product-Level Quantity Forecast (MdAPE)
✅ Model 1 trained successfully with 25 features
   🏆 Top 5 features: lag_1_quantity, seasonal_factor, rolling_mean_7, ...

📊 Model 2: Category Trend Forecast (MAPE)  
✅ Model 2 trained successfully
   📈 Category coverage: 15 categories
```

### 4. Prediction Workflow

```
┌─────────────────────────────────────────────────────────┐
│  Bước 1: Chọn sản phẩm cần dự báo                       │
│  ├── Default: Top 50 ABC products (theo doanh thu)      │
│  └── Option: Tất cả sản phẩm active (30 ngày gần nhất)  │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│  Bước 2: Load historical data (60 ngày)                 │
│  ├── Batch query tất cả products (1 query)              │
│  └── Validation: quantity > 0, revenue > 0              │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│  Bước 3: Cold Start Detection                           │
│  ├── IF product_history < 2 days:                       │
│  │   └── Use category_median * seasonal_factor / 7      │
│  └── ELSE:                                              │
│       └── Use Model 1 (XGBoost) prediction              │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│  Bước 4: Generate 7-day forecast                        │
│  ├── For each (product, future_date):                   │
│  │   ├── Create features from history + future date     │
│  │   ├── Apply seasonal factors                         │
│  │   └── Predict quantity                               │
│  └── Post-processing: Clip negative, round              │
└─────────────────────────────────────────────────────────┘
```

### 5. Data Quality Monitoring

| Metric | Threshold | Action |
|--------|-----------|--------|
| Cold start products | > 20% | 🔴 Alert in email |
| Missing dates | > 0 days | 🟡 Warning in log |
| Zero predictions | > 0 | 🔴 Alert in email |
| MdAPE | > 30% | 🟡 Review model |
| Data freshness | > 2 days | 🔴 Alert |

### 6. Email Reports

**Training Report:**
- Model metrics (MdAPE, MAPE)
- Data quality summary
- Feature importance
- Cold start count
- Alerts (nếu có)

**Forecast Report:**
- Total products forecasted
- Week-over-week comparison
- ABC distribution
- Top movers (tăng/giảm)
- Purchase order summary

---

## References

- XGBoost Documentation: https://xgboost.readthedocs.io/
- Time Series Forecasting Best Practices
- ABC Analysis in Inventory Management
- ClickHouse SQL Reference
