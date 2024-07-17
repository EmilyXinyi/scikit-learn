from ..utils._array_api import _find_matching_floating_dtype, get_namespace
from .extmath import stable_cumsum


def _weighted_percentile(array, sample_weight, percentile=50):
    """Compute weighted percentile

    Computes lower weighted percentile. If `array` is a 2D array, the
    `percentile` is computed along the axis 0.

        .. versionchanged:: 0.24
            Accepts 2D `array`.

    Parameters
    ----------
    array : 1D or 2D array
        Values to take the weighted percentile of.

    sample_weight: 1D or 2D array
        Weights for each value in `array`. Must be same shape as `array` or
        of shape `(array.shape[0],)`.

    percentile: int or float, default=50
        Percentile to compute. Must be value between 0 and 100.

    Returns
    -------
    percentile : int if `array` 1D, ndarray if `array` 2D
        Weighted percentile.
    """
    xp, _ = get_namespace(array)
    n_dim = array.ndim
    if n_dim == 0:
        return array[()]
    if array.ndim == 1:
        array = xp.reshape(array, (-1, 1))
    # When sample_weight 1D, repeat for each array.shape[1]
    if array.shape != sample_weight.shape and array.shape[0] == sample_weight.shape[0]:
        sample_weight = xp.tile(sample_weight, (array.shape[1], 1)).T
    sorted_idx = xp.argsort(array, axis=0)
    sorted_weights = _take_along_axis(sample_weight, sorted_idx, xp)

    # Find index of median prediction for each sample
    weight_cdf = stable_cumsum(sorted_weights, axis=0)
    adjusted_percentile = percentile / 100 * weight_cdf[-1]

    # For percentile=0, ignore leading observations with sample_weight=0. GH20528
    mask = adjusted_percentile == 0
    adjusted_percentile[mask] = xp.nextafter(
        adjusted_percentile[mask], adjusted_percentile[mask] + 1
    )

    percentile_idx = xp.array(
        [
            xp.searchsorted(weight_cdf[:, i], adjusted_percentile[i])
            for i in range(weight_cdf.shape[1])
        ]
    )
    percentile_idx = xp.array(percentile_idx)
    # In rare cases, percentile_idx equals to sorted_idx.shape[0]
    max_idx = sorted_idx.shape[0] - 1
    percentile_idx = xp.apply_along_axis(
        lambda x: xp.clip(x, 0, max_idx), axis=0, arr=percentile_idx
    )

    col_index = xp.arange(array.shape[1])
    percentile_in_sorted = sorted_idx[percentile_idx, col_index]
    array = xp.asarray(array)
    percentile = array[percentile_in_sorted, col_index]
    return percentile[0] if n_dim == 1 else percentile


def _take_along_axis(sample_weight, sorted_idx, xp=None):
    sorted_weights = xp.empty_like(
        sorted_idx, dtype=_find_matching_floating_dtype(sample_weight, xp=xp)
    )
    if sample_weight.ndim == 1:
        for i in range(sorted_idx.shape[0]):
            sorted_weights[i] = sample_weight[sorted_idx[i]]
        return sorted_weights
    elif sample_weight.ndim == 2:
        for j in range(sorted_idx.shape[1]):
            for i in range(sorted_idx.shape[0]):
                sorted_weights[i, j] = sample_weight[sorted_idx[i, j], j]
        return sorted_weights
    else:
        raise ValueError("Only 1D and 2D arrays are allowed")
