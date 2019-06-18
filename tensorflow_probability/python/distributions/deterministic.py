# Copyright 2018 The TensorFlow Probability Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ============================================================================
"""The Deterministic distribution class."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import abc

# Dependency imports
import six
import tensorflow.compat.v2 as tf

from tensorflow_probability.python.distributions import distribution
from tensorflow_probability.python.distributions import kullback_leibler
from tensorflow_probability.python.internal import assert_util
from tensorflow_probability.python.internal import dtype_util
from tensorflow_probability.python.internal import reparameterization
from tensorflow_probability.python.internal import tensor_util
from tensorflow_probability.python.internal import tensorshape_util

__all__ = [
    "Deterministic",
    "VectorDeterministic",
]


@six.add_metaclass(abc.ABCMeta)
class _BaseDeterministic(distribution.Distribution):
  """Base class for Deterministic distributions."""

  def __init__(self,
               loc,
               atol=None,
               rtol=None,
               is_vector=False,
               validate_args=False,
               allow_nan_stats=True,
               parameters=None,
               name="_BaseDeterministic"):
    """Initialize a batch of `_BaseDeterministic` distributions.

    The `atol` and `rtol` parameters allow for some slack in `pmf`, `cdf`
    computations, e.g. due to floating-point error.

    ```
    pmf(x; loc)
      = 1, if Abs(x - loc) <= atol + rtol * Abs(loc),
      = 0, otherwise.
    ```

    Args:
      loc: Numeric `Tensor`.  The point (or batch of points) on which this
        distribution is supported.
      atol:  Non-negative `Tensor` of same `dtype` as `loc` and broadcastable
        shape.  The absolute tolerance for comparing closeness to `loc`.
        Default is `0`.
      rtol:  Non-negative `Tensor` of same `dtype` as `loc` and broadcastable
        shape.  The relative tolerance for comparing closeness to `loc`.
        Default is `0`.
      is_vector:  Python `bool`.  If `True`, this is for `VectorDeterministic`,
        else `Deterministic`.
      validate_args: Python `bool`, default `False`. When `True` distribution
        parameters are checked for validity despite possibly degrading runtime
        performance. When `False` invalid inputs may silently render incorrect
        outputs.
      allow_nan_stats: Python `bool`, default `True`. When `True`, statistics
        (e.g., mean, mode, variance) use the value "`NaN`" to indicate the
        result is undefined. When `False`, an exception is raised if one or
        more of the statistic's batch members are undefined.
      parameters: Dict of locals to facilitate copy construction.
      name: Python `str` name prefixed to Ops created by this class.

    Raises:
      ValueError:  If `loc` is a scalar.
    """
    with tf.name_scope(name) as name:
      dtype = dtype_util.common_dtype([loc, atol, rtol], dtype_hint=tf.float32)
      self._loc = tensor_util.convert_immutable_to_tensor(
          loc, dtype_hint=dtype, name="loc")
      self._atol = tensor_util.convert_immutable_to_tensor(
          0 if atol is None else atol, dtype=dtype, name="atol")
      self._rtol = tensor_util.convert_immutable_to_tensor(
          0 if rtol is None else rtol, dtype=dtype, name="rtol")
      self._is_vector = is_vector

      super(_BaseDeterministic, self).__init__(
          dtype=self._loc.dtype,
          reparameterization_type=reparameterization.NOT_REPARAMETERIZED,
          validate_args=validate_args,
          allow_nan_stats=allow_nan_stats,
          parameters=parameters,
          graph_parents=[self._loc, self._atol, self._rtol],
          name=name)

  def _slack(self, loc):
    # Avoid using the large broadcast with self.loc if possible.
    if self.parameters["rtol"] is None:
      return self.atol
    else:
      return self.atol + self.rtol * tf.abs(loc)

  @property
  def loc(self):
    """Point (or batch of points) at which this distribution is supported."""
    return self._loc

  @property
  def atol(self):
    """Absolute tolerance for comparing points to `self.loc`."""
    return self._atol

  @property
  def rtol(self):
    """Relative tolerance for comparing points to `self.loc`."""
    return self._rtol

  def _entropy(self):
    return tf.zeros(self.batch_shape_tensor(), dtype=self.dtype)

  def _mean(self):
    return tf.identity(self.loc)

  def _variance(self):
    return tf.zeros_like(self.loc)

  def _mode(self):
    return self.mean()

  def _sample_n(self, n, seed=None):
    del seed  # unused
    return tf.broadcast_to(
        self.loc,
        tf.concat([[n], self.batch_shape_tensor(), self.event_shape_tensor()],
                  axis=0))

  def _parameter_control_dependencies(self, is_init):
    msg = "Argument loc must be at least rank 1."
    if is_init:
      if self._is_vector and tensorshape_util.rank(self.loc.shape) is not None:
        if tensorshape_util.rank(self.loc.shape) < 1:
          raise ValueError(msg)

    if not self.validate_args:
      return []

    assertions = []

    if is_init != tensor_util.is_mutable(self.loc) and self._is_vector:
      assertions.append(
          assert_util.assert_rank_at_least(self.loc, 1, message=msg))
    if is_init != tensor_util.is_mutable(self.atol):
      assertions.append(
          assert_util.assert_non_negative(
              self.atol, message="Argument 'atol' must be non-negative"))
    if is_init != tensor_util.is_mutable(self.rtol):
      assertions.append(
          assert_util.assert_non_negative(
              self.rtol, message="Argument 'rtol' must be non-negative"))
    return assertions


class Deterministic(_BaseDeterministic):
  """Scalar `Deterministic` distribution on the real line.

  The scalar `Deterministic` distribution is parameterized by a [batch] point
  `loc` on the real line.  The distribution is supported at this point only,
  and corresponds to a random variable that is constant, equal to `loc`.

  See [Degenerate rv](https://en.wikipedia.org/wiki/Degenerate_distribution).

  #### Mathematical Details

  The probability mass function (pmf) and cumulative distribution function (cdf)
  are

  ```none
  pmf(x; loc) = 1, if x == loc, else 0
  cdf(x; loc) = 1, if x >= loc, else 0
  ```

  #### Examples

  ```python
  # Initialize a single Deterministic supported at zero.
  constant = tfp.distributions.Deterministic(0.)
  constant.prob(0.)
  ==> 1.
  constant.prob(2.)
  ==> 0.

  # Initialize a [2, 2] batch of scalar constants.
  loc = [[0., 1.], [2., 3.]]
  x = [[0., 1.1], [1.99, 3.]]
  constant = tfp.distributions.Deterministic(loc)
  constant.prob(x)
  ==> [[1., 0.], [0., 1.]]
  ```

  """

  def __init__(self,
               loc,
               atol=None,
               rtol=None,
               validate_args=False,
               allow_nan_stats=True,
               name="Deterministic"):
    """Initialize a scalar `Deterministic` distribution.

    The `atol` and `rtol` parameters allow for some slack in `pmf`, `cdf`
    computations, e.g. due to floating-point error.

    ```
    pmf(x; loc)
      = 1, if Abs(x - loc) <= atol + rtol * Abs(loc),
      = 0, otherwise.
    ```

    Args:
      loc: Numeric `Tensor` of shape `[B1, ..., Bb]`, with `b >= 0`.
        The point (or batch of points) on which this distribution is supported.
      atol:  Non-negative `Tensor` of same `dtype` as `loc` and broadcastable
        shape.  The absolute tolerance for comparing closeness to `loc`.
        Default is `0`.
      rtol:  Non-negative `Tensor` of same `dtype` as `loc` and broadcastable
        shape.  The relative tolerance for comparing closeness to `loc`.
        Default is `0`.
      validate_args: Python `bool`, default `False`. When `True` distribution
        parameters are checked for validity despite possibly degrading runtime
        performance. When `False` invalid inputs may silently render incorrect
        outputs.
      allow_nan_stats: Python `bool`, default `True`. When `True`, statistics
        (e.g., mean, mode, variance) use the value "`NaN`" to indicate the
        result is undefined. When `False`, an exception is raised if one or
        more of the statistic's batch members are undefined.
      name: Python `str` name prefixed to Ops created by this class.
    """
    parameters = dict(locals())
    super(Deterministic, self).__init__(
        loc,
        atol=atol,
        rtol=rtol,
        validate_args=validate_args,
        allow_nan_stats=allow_nan_stats,
        parameters=parameters,
        name=name)

  @classmethod
  def _params_event_ndims(cls):
    return dict(loc=0, atol=0, rtol=0)

  def _batch_shape_tensor(self):
    return tf.broadcast_dynamic_shape(
        tf.shape(self.loc),
        tf.broadcast_dynamic_shape(tf.shape(self.atol), tf.shape(self.rtol)))

  def _batch_shape(self):
    return tf.broadcast_static_shape(
        self.loc.shape,
        tf.broadcast_static_shape(self.atol.shape, self.rtol.shape))

  def _event_shape_tensor(self):
    return tf.constant([], dtype=tf.int32)

  def _event_shape(self):
    return tf.TensorShape([])

  def _prob(self, x):
    loc = tf.identity(self.loc)
    # Enforces dtype of probability to be float, when self.dtype is not.
    prob_dtype = self.dtype if self.dtype.is_floating else tf.float32
    return tf.cast(tf.abs(x - loc) <= self._slack(loc), dtype=prob_dtype)

  def _cdf(self, x):
    loc = tf.identity(self.loc)
    return tf.cast(x >= loc - self._slack(loc), dtype=self.dtype)


class VectorDeterministic(_BaseDeterministic):
  """Vector `Deterministic` distribution on `R^k`.

  The `VectorDeterministic` distribution is parameterized by a [batch] point
  `loc in R^k`.  The distribution is supported at this point only,
  and corresponds to a random variable that is constant, equal to `loc`.

  See [Degenerate rv](https://en.wikipedia.org/wiki/Degenerate_distribution).

  #### Mathematical Details

  The probability mass function (pmf) is

  ```none
  pmf(x; loc)
    = 1, if All[Abs(x - loc) <= atol + rtol * Abs(loc)],
    = 0, otherwise.
  ```

  #### Examples

  ```python
  tfd = tfp.distributions

  # Initialize a single VectorDeterministic supported at [0., 2.] in R^2.
  constant = tfd.Deterministic([0., 2.])
  constant.prob([0., 2.])
  ==> 1.
  constant.prob([0., 3.])
  ==> 0.

  # Initialize a [3] batch of constants on R^2.
  loc = [[0., 1.], [2., 3.], [4., 5.]]
  constant = tfd.VectorDeterministic(loc)
  constant.prob([[0., 1.], [1.9, 3.], [3.99, 5.]])
  ==> [1., 0., 0.]
  ```

  """

  def __init__(self,
               loc,
               atol=None,
               rtol=None,
               validate_args=False,
               allow_nan_stats=True,
               name="VectorDeterministic"):
    """Initialize a `VectorDeterministic` distribution on `R^k`, for `k >= 0`.

    Note that there is only one point in `R^0`, the "point" `[]`.  So if `k = 0`
    then `self.prob([]) == 1`.

    The `atol` and `rtol` parameters allow for some slack in `pmf`
    computations, e.g. due to floating-point error.

    ```
    pmf(x; loc)
      = 1, if All[Abs(x - loc) <= atol + rtol * Abs(loc)],
      = 0, otherwise
    ```

    Args:
      loc: Numeric `Tensor` of shape `[B1, ..., Bb, k]`, with `b >= 0`, `k >= 0`
        The point (or batch of points) on which this distribution is supported.
      atol:  Non-negative `Tensor` of same `dtype` as `loc` and broadcastable
        shape.  The absolute tolerance for comparing closeness to `loc`.
        Default is `0`.
      rtol:  Non-negative `Tensor` of same `dtype` as `loc` and broadcastable
        shape.  The relative tolerance for comparing closeness to `loc`.
        Default is `0`.
      validate_args: Python `bool`, default `False`. When `True` distribution
        parameters are checked for validity despite possibly degrading runtime
        performance. When `False` invalid inputs may silently render incorrect
        outputs.
      allow_nan_stats: Python `bool`, default `True`. When `True`, statistics
        (e.g., mean, mode, variance) use the value "`NaN`" to indicate the
        result is undefined. When `False`, an exception is raised if one or
        more of the statistic's batch members are undefined.
      name: Python `str` name prefixed to Ops created by this class.
    """
    parameters = dict(locals())
    super(VectorDeterministic, self).__init__(
        loc,
        atol=atol,
        rtol=rtol,
        is_vector=True,
        validate_args=validate_args,
        allow_nan_stats=allow_nan_stats,
        parameters=parameters,
        name=name)

  @classmethod
  def _params_event_ndims(cls):
    return dict(loc=1, atol=1, rtol=1)

  def _batch_shape_tensor(self):
    return tf.broadcast_dynamic_shape(
        tf.shape(self.loc),
        tf.broadcast_dynamic_shape(tf.shape(self.atol),
                                   tf.shape(self.rtol)))[:-1]

  def _batch_shape(self):
    return tf.broadcast_static_shape(
        self.loc.shape,
        tf.broadcast_static_shape(self.atol.shape, self.rtol.shape))[:-1]

  def _event_shape_tensor(self):
    return tf.shape(self.loc)[-1:]

  def _event_shape(self):
    return self.loc.shape[-1:]

  def _prob(self, x):
    if self.validate_args:
      is_vector_check = assert_util.assert_rank_at_least(x, 1)
      right_vec_space_check = assert_util.assert_equal(
          self.event_shape_tensor(),
          tf.gather(tf.shape(x),
                    tf.rank(x) - 1),
          message="Argument 'x' not defined in the same space R^k as this distribution"
      )
      with tf.control_dependencies([is_vector_check]):
        with tf.control_dependencies([right_vec_space_check]):
          x = tf.identity(x)
    loc = tf.identity(self.loc)
    return tf.cast(
        tf.reduce_all(
            input_tensor=tf.abs(x - loc) <= self._slack(loc), axis=-1),
        dtype=self.dtype)


@kullback_leibler.RegisterKL(_BaseDeterministic, distribution.Distribution)
def _kl_deterministic_distribution(a, b, name=None):
  """Calculate the batched KL divergence `KL(a || b)` with `a` Deterministic.

  Args:
    a: instance of a Deterministic distribution object.
    b: instance of a Distribution distribution object.
    name: (optional) Name to use for created operations. Default is
      "kl_deterministic_distribution".

  Returns:
    Batchwise `KL(a || b)`.
  """
  with tf.name_scope(name or "kl_deterministic_distribution"):
    return -b.log_prob(a.loc)
