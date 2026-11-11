
import pandas as pd
import numpy as np
import joblib

from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# ==========================================
# EXPERIMENT 5: NORMALIZED HISTORICAL FEATURES
# ==========================================

# Load datasets
stock_data = pd.read_csv("stock_data.csv")
future_prices = pd.read_csv("future_stock_prices.csv")

# Match current prices with future prices
data = pd.merge(
    stock_data,
    future_prices,
    on=["symbol", "ts_utc"]
)

# Convert timestamps and sort each stock chronologically
data["ts_utc"] = pd.to_datetime(data["ts_utc"])

data = data.sort_values(
    by=["symbol", "ts_utc"]
).copy()

# ==========================================
# CREATE NORMALIZED FEATURES
# ==========================================

# 1. Percentage price change over previous 5 minutes
previous_close = data.groupby("symbol")["close"].shift(1)

data["return_1"] = (
    (data["close"] - previous_close) / previous_close
) * 100

# 2. Percentage price change over previous 15 minutes
close_15_minutes_ago = (
    data.groupby("symbol")["close"].shift(3)
)

data["return_3"] = (
    (data["close"] - close_15_minutes_ago)
    / close_15_minutes_ago
) * 100

# 3. Percentage change in volume from previous interval
previous_volume = data.groupby("symbol")["volume"].shift(1)

data["volume_change"] = (
    (data["volume"] - previous_volume)
    / previous_volume
) * 100

# 4. Price range as a percentage of closing price
data["range_percent"] = (
    data["price_range"] / data["close"]
) * 100

# ==========================================
# CREATE TARGET
# ==========================================

data["percentage_change"] = (
    (data["future_close"] - data["close"])
    / data["close"]
) * 100

# Remove missing and infinite values
data = data.replace([np.inf, -np.inf], np.nan)
data = data.dropna().copy()

print("=== EXPERIMENT 5 DATASET ===")
print("Matched records:", len(data))

print("\nAvailable stocks:")
print(data["symbol"].unique())

print("\nAverage percentage change:")
print(data["percentage_change"].mean())

# ==========================================
# SELECT INPUTS AND TARGET
# ==========================================

features = [
    "return_1",
    "return_3",
    "volume_change",
    "range_percent"
]

target = "percentage_change"

# ==========================================
# SPLIT TRAINING AND TESTING DATA
# ==========================================

data["date"] = data["ts_utc"].dt.date

training_data = data[
    data["date"] < pd.to_datetime("2025-10-01").date()
].copy()

testing_data = data[
    (data["date"] >= pd.to_datetime("2025-10-01").date()) &
    (data["date"] < pd.to_datetime("2025-11-01").date())
].copy()

X_train = training_data[features]
y_train = training_data[target]

X_test = testing_data[features]
y_test = testing_data[target]

print("\n=== TRAINING AND TESTING ===")
print("Training records:", len(X_train))
print("Testing records:", len(X_test))

# ==========================================
# TRAIN LINEAR REGRESSION MODEL
# ==========================================

model = LinearRegression()

model.fit(X_train, y_train)

# Generate predictions
predictions = model.predict(X_test)

# ==========================================
# EVALUATE MODEL
# ==========================================

mae = mean_absolute_error(y_test, predictions)

mse = mean_squared_error(y_test, predictions)

rmse = np.sqrt(mse)

r_squared = r2_score(y_test, predictions)

print("\n=== EXPERIMENT 5 MODEL PERFORMANCE ===")
print(f"MAE: {mae:.6f}")
print(f"MSE: {mse:.6f}")
print(f"RMSE: {rmse:.6f}")
print(f"R-squared: {r_squared:.6f}")

# ==========================================
# BASELINE COMPARISON
# ==========================================

# Baseline predicts zero percentage change
baseline_predictions = np.zeros(len(y_test))

baseline_mae = mean_absolute_error(
    y_test, baseline_predictions
)

baseline_rmse = np.sqrt(
    mean_squared_error(y_test, baseline_predictions)
)

print("\n=== BASELINE COMPARISON ===")
print(f"Baseline MAE: {baseline_mae:.6f}")
print(f"Model MAE: {mae:.6f}")
print(f"Baseline RMSE: {baseline_rmse:.6f}")
print(f"Model RMSE: {rmse:.6f}")

# ==========================================
# MODEL COEFFICIENTS
# ==========================================

print("\n=== MODEL COEFFICIENTS ===")

for feature, coefficient in zip(features, model.coef_):
    print(f"{feature}: {coefficient:.10f}")

print(f"Intercept: {model.intercept_:.10f}")

# ==========================================
# SAVE PREDICTIONS
# ==========================================

testing_data["predicted_percentage_change"] = predictions

testing_data["actual_percentage_change"] = y_test

testing_data.to_csv(
    "experiment5_predictions.csv",
    index=False
)

print("\nPredictions saved to experiment5_predictions.csv")

# ==========================================
# PERFORMANCE BY STOCK
# ==========================================

print("\n=== PERFORMANCE BY STOCK ===")

for symbol in testing_data["symbol"].unique():

    stock_results = testing_data[
        testing_data["symbol"] == symbol
    ]

    stock_mae = mean_absolute_error(
        stock_results["actual_percentage_change"],
        stock_results["predicted_percentage_change"]
    )

    print(f"{symbol} MAE: {stock_mae:.6f}")

# ==========================================
# SAVE MODEL
# ==========================================

joblib.dump(model, "experiment5_model.pkl")

print("\nExperiment 5 model saved!")
print("Program completed!")
