
import pandas as pd
import numpy as np
import joblib

from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# ==========================================
# EXPERIMENT 3: PREDICTING PERCENTAGE CHANGE
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

# Calculate percentage price change
data["percentage_change"] = (
    (data["future_close"] - data["close"]) / data["close"]
) * 100

# Remove missing or invalid values
data = data.replace([np.inf, -np.inf], np.nan)
data = data.dropna()

print("=== EXPERIMENT 3 DATASET ===")
print("Matched records:", len(data))
print("\nAvailable stocks:")
print(data["symbol"].unique())

print("\nAverage percentage change:")
print(data["percentage_change"].mean())

# ==========================================
# SELECT INPUTS AND TARGET
# ==========================================

features = ["close", "volume", "price_range"]
target = "percentage_change"

X = data[features]
y = data[target]

# ==========================================
# SPLIT TRAINING AND TESTING DATA
# ==========================================

data["date"] = pd.to_datetime(data["ts_utc"]).dt.date

training_data = data[
    data["date"] < pd.to_datetime("2025-10-01").date()
]

testing_data = data[
    (data["date"] >= pd.to_datetime("2025-10-01").date()) &
    (data["date"] < pd.to_datetime("2025-11-01").date())
]

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

print("\n=== EXPERIMENT 3 MODEL PERFORMANCE ===")
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

testing_data = testing_data.copy()
testing_data["predicted_percentage_change"] = predictions

testing_data["actual_percentage_change"] = y_test

testing_data.to_csv(
    "experiment3_predictions.csv",
    index=False
)

print("\nPredictions saved to experiment3_predictions.csv")

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

joblib.dump(model, "experiment3_model.pkl")

print("\nExperiment 3 model saved!")
print("Program completed!")
