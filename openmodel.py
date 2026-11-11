import joblib

# Load your saved model
model = joblib.load("stock_price_predictor.pkl")

print("Model loaded successfully!")

# Display model information
print("\nModel coefficients:")
print(model.coef_)

print("\nModel intercept:")
print(model.intercept_)

print("\nModel features:")
print(model.feature_names_in_)
