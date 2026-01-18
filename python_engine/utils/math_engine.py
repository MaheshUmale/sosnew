import math
from scipy.stats import norm
from scipy.optimize import newton

class MathEngine:
    @staticmethod
    def black_scholes(S, K, T, r, sigma, option_type='CE'):
        """
        Calculates the theoretical price of an option using the Black-Scholes model.
        S: Spot Price
        K: Strike Price
        T: Time to Expiry (in years)
        r: Risk-free rate (e.g., 0.1 for 10%)
        sigma: Implied Volatility (e.g., 0.2 for 20%)
        """
        if T <= 0:
            return max(0, S - K) if option_type == 'CE' else max(0, K - S)

        d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)

        if option_type == 'CE':
            price = S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
        else:
            price = K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

        return price

    @staticmethod
    def calculate_iv(price, S, K, T, r, option_type='CE'):
        """
        Calculates Implied Volatility using Newton-Raphson.
        """
        if T <= 0 or price <= 0:
            return 0.0

        def objective_function(sigma):
            return MathEngine.black_scholes(S, K, T, r, sigma, option_type) - price

        try:
            # Initial guess: 20% volatility
            iv = newton(objective_function, 0.2, tol=1e-5, maxiter=100)
            return iv if iv > 0 else 0.0
        except Exception:
            return 0.0

    @staticmethod
    def calculate_greeks(S, K, T, r, sigma, option_type='CE'):
        """
        Calculates Delta and Theta for an option.
        """
        if T <= 0 or sigma <= 0:
            return {'delta': 0.0, 'theta': 0.0}

        d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)

        if option_type == 'CE':
            delta = norm.cdf(d1)
            # Daily Theta
            theta = (-(S * norm.pdf(d1) * sigma) / (2 * math.sqrt(T)) -
                     r * K * math.exp(-r * T) * norm.cdf(d2)) / 365
        else:
            delta = norm.cdf(d1) - 1
            theta = (-(S * norm.pdf(d1) * sigma) / (2 * math.sqrt(T)) +
                     r * K * math.exp(-r * T) * norm.cdf(-d2)) / 365

        return {
            'delta': round(delta, 4),
            'theta': round(theta, 4)
        }

    @staticmethod
    def get_smart_trend(price_change, oi_change):
        """
        Determines the trend sentiment based on Price and OI changes.
        """
        if price_change > 0 and oi_change > 0:
            return "Long Buildup"
        elif price_change < 0 and oi_change > 0:
            return "Short Buildup"
        elif price_change < 0 and oi_change < 0:
            return "Long Unwinding"
        elif price_change > 0 and oi_change < 0:
            return "Short Covering"
        else:
            return "Neutral"
