"""Hierarchical Risk Parity (HRP) Portfolio Optimizer."""
import numpy as np
import pandas as pd
import scipy.cluster.hierarchy as sch
import scipy.spatial.distance as ssd
from typing import List

class HRPOptimizer:
    """
    Implements Marcos Lopez de Prado's Hierarchical Risk Parity algorithm.
    """
    
    @staticmethod
    def get_corr_matrix(prices: pd.DataFrame) -> np.ndarray:
        returns = prices.pct_change().dropna()
        return returns.corr().values

    @staticmethod
    def get_cov_matrix(prices: pd.DataFrame) -> np.ndarray:
        returns = prices.pct_change().dropna()
        return returns.cov().values

    @staticmethod
    def _get_cluster_var(cov: np.ndarray, items: List[int]) -> float:
        """Calculate the variance of a cluster of assets."""
        cov_slice = cov[np.ix_(items, items)]
        w = np.ones(len(items)) / len(items)
        return np.dot(w.T, np.dot(cov_slice, w))

    @staticmethod
    def _get_quasi_diag(link: np.ndarray, n_items: int) -> List[int]:
        """Sort items by hierarchical clustering (Optimal Leaf Ordering)."""
        link = link.astype(int)
        sort_idx = pd.Series([link[-1, 0], link[-1, 1]])
        
        while sort_idx.max() >= n_items:
            sort_idx.index = range(0, sort_idx.shape[0] * 2, 2)
            df0 = sort_idx[sort_idx >= n_items]
            i = df0.index
            
            # FIX: Explicitly cast to int to prevent NumPy indexing errors
            j = (df0.values - n_items).astype(int) 
            
            sort_idx[i] = link[j, 0]
            
            df0 = pd.Series(link[j, 1], index=i + 1)
            sort_idx = pd.concat([sort_idx, df0])
            sort_idx = sort_idx.sort_index()
            
        return sort_idx.tolist()

    @staticmethod
    def _get_recursive_bisection(cov: np.ndarray, items: List[int]) -> pd.Series:
        """Recursive bisection to allocate weights based on cluster variance."""
        w = pd.Series(1.0, index=items)
        c_items = [items]
        
        while len(c_items) > 0:
            c_items_new = []
            for i in c_items:
                if len(i) > 1:
                    mid = len(i) // 2
                    c_items_new.append(i[:mid])
                    c_items_new.append(i[mid:])
            c_items = c_items_new
            
            for i in range(0, len(c_items), 2):
                if i + 1 < len(c_items):
                    left = c_items[i]
                    right = c_items[i+1]
                    
                    var_left = HRPOptimizer._get_cluster_var(cov, left)
                    var_right = HRPOptimizer._get_cluster_var(cov, right)
                    
                    alpha = 1 - var_left / (var_left + var_right)
                    
                    w[left] *= alpha
                    w[right] *= (1 - alpha)
                    
        return w

    @classmethod
    def optimize(cls, prices: pd.DataFrame) -> dict:
        """Main entry point. Returns HRP weights."""
        if prices.empty or len(prices.columns) < 2:
            return {"error": "Need at least 2 assets for HRP"}
            
        # Drop columns with too many NaNs (common in yfinance batch downloads)
        prices = prices.dropna(axis=1, thresh=int(len(prices) * 0.5))
        if len(prices.columns) < 2:
            return {"error": "Need at least 2 assets with valid data for HRP"}

        cov = cls.get_cov_matrix(prices)
        corr = cls.get_corr_matrix(prices)
        
        # Math safety guards for real-world messy data
        corr = np.nan_to_num(corr, nan=0.0)
        np.fill_diagonal(corr, 1.0)
        
        # Distance matrix: sqrt(0.5 * (1 - corr))
        # Clip to 0 to prevent sqrt of negative numbers caused by floating point drift
        dist = np.sqrt(np.clip(0.5 * (1 - corr), 0, None))
        
        # Hierarchical Clustering
        link = sch.linkage(ssd.squareform(dist), method='single')
        
        n_items = len(prices.columns)
        sort_idx = cls._get_quasi_diag(link, n_items)
        
        weights = cls._get_recursive_bisection(cov, sort_idx)
        weights.index = prices.columns
        
        return {
            "weights": weights.to_dict(),
            "clusters": sort_idx,
            "symbols": prices.columns.tolist()
        }
