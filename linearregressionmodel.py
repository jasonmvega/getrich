
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score
)
import joblib

# ==========================================
# 1. LOAD CSV FILES
# ==========================================

stock_data = pd.read_csv("stock_data.csv")
future_data = pd.read_csv("future_stock_prices.csv")

# Convert timestamps to UTC
stock_data["ts_utc"] = pd.to_datetime(
    stock_data["ts_utc"], utc=True
)

future_data["ts_utc"] = pd.to_datetime(
    future_data["ts_utc"], utc=True
)

# ==========================================
# 2. MERGE DATA
# ==========================================

data = pd.merge(
    stock_data,
    future_data,
    on=["symbol", "ts_utc"],
    how="inner"
)

data = data.dropna(
    subset=["close", "volume", "price_range", "future_close"]
)

data = data.sort_values("ts_utc").reset_index(drop=True)

print("\n=== DATASET INFORMATION ===")

print("Current stock records:", len(stock_data))
print("Future price records:", len(future_data))
print("Matched records:", len(data))

print("\nAvailable stocks:")
print(data["symbol"].unique())

if data.empty:
    raise ValueError(
        "No matching records. Check your CSV files."
    )

# ==========================================
# 3. TRAINING AND TESTING SPLIT
# ==========================================

training_mask = (
    (data["ts_utc"] >= "2025-01-01")
    & (data["ts_utc"] < "2025-10-01")
)

testing_mask = (
    (data["ts_utc"] >= "2025-10-01")
    & (data["ts_utc"] < "2025-11-01")
)

training_data = data[training_mask]
testing_data = data[testing_mask]

print("\n=== TRAINING AND TESTING ===")

print("Training records:", len(training_data))
print("Testing records:", len(testing_data))

print("Training stocks:", training_data["symbol"].unique())
print("Testing stocks:", testing_data["symbol"].unique())

if training_data.empty or testing_data.empty:
    raise ValueError(
        "Training or testing data is empty. "
        "Check your CSV files and date ranges."
    )

# ==========================================
# 4. SELECT FEATURES AND TARGET
# ==========================================

features = [
    "close",
    "volume",
    "price_range"
]

X_train = training_data[features]
y_train = training_data["future_close"]

X_test = testing_data[features]
y_test = testing_data["future_close"]

# ==========================================
# 5. TRAIN LINEAR REGRESSION MODEL
# ==========================================

model = LinearRegression()

model.fit(X_train, y_train)

# Generate predictions
y_pred = model.predict(X_test)

# ==========================================
# 6. EVALUATE MODEL
# ==========================================

mae = mean_absolute_error(y_test, y_pred)
mse = mean_squared_error(y_test, y_pred)
rmse = np.sqrt(mse)
r2 = r2_score(y_test, y_pred)

print("\n=== MODEL PERFORMANCE ===")

print(f"Mean Absolute Error: {mae:.4f}")
print(f"Mean Squared Error: {mse:.4f}")
print(f"Root Mean Squared Error: {rmse:.4f}")
print(f"R-squared: {r2:.4f}")

# ==========================================
# 7. DISPLAY MODEL COEFFICIENTS
# ==========================================

print("\n=== MODEL COEFFICIENTS ===")

for feature, coefficient in zip(features, model.coef_):
    print(f"{feature}: {coefficient:.6f}")

print("Intercept:", model.intercept_)

# ==========================================
# 8. SAVE PREDICTIONS
# ==========================================

results = testing_data[
    ["symbol", "ts_utc", "close", "future_close"]
].copy()

results["predicted_future_close"] = y_pred

results["predicted_price_change"] = (
    results["predicted_future_close"] - results["close"]
)

results.to_csv("stock_predictions.csv", index=False)

print("\nPredictions saved to stock_predictions.csv")

# ==========================================
# 9. EVALUATE EACH STOCK
# ==========================================

print("\n=== PERFORMANCE BY STOCK ===")

for symbol in testing_data["symbol"].unique():

    stock_results = results[
        results["symbol"] == symbol
    ]

    stock_mae = mean_absolute_error(
        stock_results["future_close"],
        stock_results["predicted_future_close"]
    )

    print(f"\n{symbol} MAE: {stock_mae:.4f}")

# ==========================================
# 10. SAVE MODEL
# ==========================================

joblib.dump(model, "stock_price_predictor.pkl")

print("\nModel saved successfully!")
print("Program completed!")


# ==========================================
# BASELINE COMPARISON
# ==========================================

baseline_predictions = testing_data["close"]

baseline_mae = mean_absolute_error(
    y_test,
    baseline_predictions
)

baseline_rmse = np.sqrt(
    mean_squared_error(y_test, baseline_predictions)
)

print("\n=== BASELINE COMPARISON ===")

print(f"Baseline MAE: {baseline_mae:.4f}")
print(f"Model MAE: {mae:.4f}")

print(f"Baseline RMSE: {baseline_rmse:.4f}")
print(f"Model RMSE: {rmse:.4f}")

