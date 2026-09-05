use crate::{InferenceError, Result};
use serde::{Deserialize, Deserializer, Serialize, Serializer};
use std::sync::Arc;

#[derive(Debug, Clone)]
pub struct Tensor {
    pub data: Arc<Vec<f32>>,
    pub shape: Vec<usize>,
    pub dtype: TensorDtype,
}

impl Serialize for Tensor {
    fn serialize<S>(&self, serializer: S) -> std::result::Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        use serde::ser::SerializeStruct;
        let mut state = serializer.serialize_struct("Tensor", 3)?;
        state.serialize_field("data", self.data.as_ref())?;
        state.serialize_field("shape", &self.shape)?;
        state.serialize_field("dtype", &self.dtype)?;
        state.end()
    }
}

impl<'de> Deserialize<'de> for Tensor {
    fn deserialize<D>(deserializer: D) -> std::result::Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        use serde::de::{self, MapAccess, Visitor};
        use std::fmt;

        #[derive(Deserialize)]
        #[serde(field_identifier, rename_all = "lowercase")]
        enum Field {
            Data,
            Shape,
            Dtype,
        }

        struct TensorVisitor;

        impl<'de> Visitor<'de> for TensorVisitor {
            type Value = Tensor;

            fn expecting(&self, formatter: &mut fmt::Formatter) -> fmt::Result {
                formatter.write_str("struct Tensor")
            }

            fn visit_map<V>(self, mut map: V) -> std::result::Result<Tensor, V::Error>
            where
                V: MapAccess<'de>,
            {
                let mut data: Option<Vec<f32>> = None;
                let mut shape: Option<Vec<usize>> = None;
                let mut dtype: Option<TensorDtype> = None;

                while let Some(key) = map.next_key()? {
                    match key {
                        Field::Data => {
                            if data.is_some() {
                                return Err(de::Error::duplicate_field("data"));
                            }
                            data = Some(map.next_value()?);
                        }
                        Field::Shape => {
                            if shape.is_some() {
                                return Err(de::Error::duplicate_field("shape"));
                            }
                            shape = Some(map.next_value()?);
                        }
                        Field::Dtype => {
                            if dtype.is_some() {
                                return Err(de::Error::duplicate_field("dtype"));
                            }
                            dtype = Some(map.next_value()?);
                        }
                    }
                }

                let data = data.ok_or_else(|| de::Error::missing_field("data"))?;
                let shape = shape.ok_or_else(|| de::Error::missing_field("shape"))?;
                let dtype = dtype.ok_or_else(|| de::Error::missing_field("dtype"))?;

                Ok(Tensor {
                    data: Arc::new(data),
                    shape,
                    dtype,
                })
            }
        }

        deserializer.deserialize_struct("Tensor", &["data", "shape", "dtype"], TensorVisitor)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum TensorDtype {
    Float32,
    Int8,
    Float16,
}

impl Tensor {
    pub fn new(data: Vec<f32>, shape: Vec<usize>) -> Result<Self> {
        let expected_size: usize = shape.iter().product();
        if data.len() != expected_size {
            return Err(InferenceError::ShapeMismatch {
                expected: format!("{:?}", shape),
                actual: format!("size {}", data.len()),
            });
        }
        Ok(Tensor {
            data: Arc::new(data),
            shape,
            dtype: TensorDtype::Float32,
        })
    }

    pub fn zeros(shape: Vec<usize>) -> Self {
        let size: usize = shape.iter().product();
        Tensor {
            data: Arc::new(vec![0.0; size]),
            shape,
            dtype: TensorDtype::Float32,
        }
    }

    pub fn shape(&self) -> &[usize] {
        &self.shape
    }

    pub fn size(&self) -> usize {
        self.data.len()
    }

    pub fn flatten(&self) -> Vec<f32> {
        self.data.as_ref().clone()
    }

    pub fn quantize_int8(&self) -> Result<Tensor> {
        let min = self.data.iter().cloned().fold(f32::INFINITY, f32::min);
        let max = self.data.iter().cloned().fold(f32::NEG_INFINITY, f32::max);

        let scale = (max - min) / 255.0;
        if scale <= 0.0 {
            return Err(InferenceError::QuantizationError(
                "Invalid scale for quantization".to_string(),
            ));
        }

        let quantized = self
            .data
            .iter()
            .map(|&v| ((v - min) / scale).clamp(0.0, 255.0))
            .collect::<Vec<f32>>();

        Ok(Tensor {
            data: Arc::new(quantized),
            shape: self.shape.clone(),
            dtype: TensorDtype::Int8,
        })
    }

    pub fn dequantize_int8(&self, scale: f32, offset: f32) -> Result<Tensor> {
        let dequantized = self
            .data
            .iter()
            .map(|&v| v * scale + offset)
            .collect::<Vec<f32>>();

        Ok(Tensor {
            data: Arc::new(dequantized),
            shape: self.shape.clone(),
            dtype: TensorDtype::Float32,
        })
    }

    pub fn matmul(&self, other: &Tensor) -> Result<Tensor> {
        if self.shape.len() != 2 || other.shape.len() != 2 {
            return Err(InferenceError::ShapeMismatch {
                expected: "2D tensors".to_string(),
                actual: format!("{:?} x {:?}", self.shape, other.shape),
            });
        }

        let (m, k) = (self.shape[0], self.shape[1]);
        let (k2, n) = (other.shape[0], other.shape[1]);

        if k != k2 {
            return Err(InferenceError::ShapeMismatch {
                expected: format!("inner dimension {} match", k),
                actual: format!("got {} and {}", k, k2),
            });
        }

        let mut result = vec![0.0; m * n];
        for i in 0..m {
            for j in 0..n {
                let mut sum = 0.0;
                for l in 0..k {
                    sum += self.data[i * k + l] * other.data[l * n + j];
                }
                result[i * n + j] = sum;
            }
        }

        Tensor::new(result, vec![m, n])
    }

    pub fn relu(&self) -> Result<Tensor> {
        let relu_data = self.data.iter().map(|&x| x.max(0.0)).collect();
        Ok(Tensor {
            data: Arc::new(relu_data),
            shape: self.shape.clone(),
            dtype: self.dtype,
        })
    }

    pub fn softmax(&self) -> Result<Tensor> {
        if self.shape.len() != 1 {
            return Err(InferenceError::ShapeMismatch {
                expected: "1D tensor".to_string(),
                actual: format!("{:?}", self.shape),
            });
        }

        let max = self.data.iter().cloned().fold(f32::NEG_INFINITY, f32::max);
        let exp: Vec<f32> = self.data.iter().map(|&x| (x - max).exp()).collect();
        let sum: f32 = exp.iter().sum();

        let softmax_data = exp.iter().map(|&x| x / sum).collect();

        Ok(Tensor {
            data: Arc::new(softmax_data),
            shape: self.shape.clone(),
            dtype: TensorDtype::Float32,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_tensor_creation() {
        let data = vec![1.0, 2.0, 3.0, 4.0];
        let tensor = Tensor::new(data.clone(), vec![2, 2]).unwrap();
        assert_eq!(tensor.shape(), &[2, 2]);
        assert_eq!(tensor.size(), 4);
    }

    #[test]
    fn test_tensor_shape_mismatch() {
        let data = vec![1.0, 2.0];
        let result = Tensor::new(data, vec![3, 3]);
        assert!(result.is_err());
    }

    #[test]
    fn test_tensor_zeros() {
        let tensor = Tensor::zeros(vec![3, 3]);
        assert_eq!(tensor.size(), 9);
        assert!(tensor.data.iter().all(|&x| x == 0.0));
    }

    #[test]
    fn test_tensor_flatten() {
        let data = vec![1.0, 2.0, 3.0, 4.0];
        let tensor = Tensor::new(data.clone(), vec![2, 2]).unwrap();
        let flat = tensor.flatten();
        assert_eq!(flat, data);
    }

    #[test]
    fn test_matmul() {
        let a = Tensor::new(vec![1.0, 2.0, 3.0, 4.0], vec![2, 2]).unwrap();
        let b = Tensor::new(vec![5.0, 6.0, 7.0, 8.0], vec![2, 2]).unwrap();
        let c = a.matmul(&b).unwrap();

        // [1*5 + 2*7, 1*6 + 2*8] = [19, 22]
        // [3*5 + 4*7, 3*6 + 4*8] = [43, 50]
        assert_eq!(c.flatten(), vec![19.0, 22.0, 43.0, 50.0]);
    }

    #[test]
    fn test_matmul_shape_mismatch() {
        let a = Tensor::new(vec![1.0, 2.0], vec![1, 2]).unwrap();
        let b = Tensor::new(vec![3.0, 4.0, 5.0], vec![3, 1]).unwrap();
        assert!(a.matmul(&b).is_err());
    }

    #[test]
    fn test_relu() {
        let data = vec![-1.0, -2.0, 3.0, 0.5];
        let tensor = Tensor::new(data, vec![2, 2]).unwrap();
        let relu_tensor = tensor.relu().unwrap();
        assert_eq!(relu_tensor.flatten(), vec![0.0, 0.0, 3.0, 0.5]);
    }

    #[test]
    fn test_softmax() {
        let data = vec![1.0, 2.0, 3.0];
        let tensor = Tensor::new(data, vec![3]).unwrap();
        let softmax_tensor = tensor.softmax().unwrap();
        let softmax_data = softmax_tensor.flatten();

        // Check sum to 1 (within float precision)
        let sum: f32 = softmax_data.iter().sum();
        assert!((sum - 1.0).abs() < 1e-6);
    }

    #[test]
    fn test_quantize_int8() {
        let data = vec![0.0, 64.0, 128.0, 255.0];
        let tensor = Tensor::new(data, vec![2, 2]).unwrap();
        let quantized = tensor.quantize_int8().unwrap();

        assert_eq!(quantized.dtype, TensorDtype::Int8);
        assert_eq!(quantized.shape, vec![2, 2]);
    }

    #[test]
    fn test_dequantize_int8() {
        let data = vec![0.0, 127.0, 254.0, 255.0];
        let tensor = Tensor::new(data, vec![2, 2]).unwrap();
        let dequantized = tensor.dequantize_int8(0.5, 10.0).unwrap();

        assert_eq!(dequantized.dtype, TensorDtype::Float32);
        assert_eq!(dequantized.flatten()[0], 10.0);
        assert_eq!(dequantized.flatten()[1], 10.0 + 127.0 * 0.5);
    }
}
