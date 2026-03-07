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
| Feature | Mô tả |
|---------|-------|
| `lag_1_quantity` | Số lượng bán hôm qua |
| `lag_7_quantity` | Số lượng bán cách đây 1 tuần |
| `lag_14_quantity` | Số lượng bán cách đây 2 tuần |
| `lag_30_quantity` | Số lượng bán cách đây 1 tháng |

**Adaptive behavior**: Nếu dữ liệu < 30 ngày, tự động bỏ lag 30.

**Tinh chỉnh**: 
- Thêm lag 3 ngày → capture short-term trends
- Bỏ lag 30 → khi dữ liệu ngắn, tránh overfitting

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

## Data Quality Indicators

### Warning signs

| Issue | Dấu hiệu | Cách xử lý |
|-------|----------|------------|
| **Cold start** | < 7 ngày data | Dùng category average |
| **Outliers** | MdAPE > 50% | Check data quality |
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

### 4. Handling New Products
- Cold start problem: Dùng category average
- Warm up: Sau 7-14 ngày có thể dự báo
- Full: Sau 30+ ngày

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

### Alert Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| MdAPE | > 25% | > 35% |
| Missing forecasts | > 5% | > 15% |
| Data latency | > 2 days | > 5 days |

---

## References

- XGBoost Documentation: https://xgboost.readthedocs.io/
- Time Series Forecasting Best Practices
- ABC Analysis in Inventory Management
