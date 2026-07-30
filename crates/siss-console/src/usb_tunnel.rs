use crate::types::ConsoleError;
use std::sync::Arc;
use tokio::sync::Mutex;

const START_BYTE: u8 = 0xFF;
const BAUDRATE: u32 = 115200;

#[derive(Debug, Clone)]
pub struct Frame {
    pub payload: Vec<u8>,
}

impl Frame {
    pub fn new(payload: Vec<u8>) -> Self {
        Self { payload }
    }

    pub fn encode(&self) -> Result<Vec<u8>, ConsoleError> {
        let mut buffer = Vec::new();
        buffer.push(START_BYTE);

        let len = self.payload.len() as u16;
        buffer.extend_from_slice(&len.to_le_bytes());
        buffer.extend_from_slice(&self.payload);

        let crc = Self::compute_crc(&self.payload);
        buffer.extend_from_slice(&crc.to_le_bytes());

        Ok(buffer)
    }

    pub fn decode(data: &[u8]) -> Result<Self, ConsoleError> {
        if data.len() < 5 {
            return Err(ConsoleError::FrameError(
                "Frame too short (min 5 bytes)".to_string(),
            ));
        }

        if data[0] != START_BYTE {
            return Err(ConsoleError::FrameError("Invalid start byte".to_string()));
        }

        let len = u16::from_le_bytes([data[1], data[2]]) as usize;
        if data.len() < 5 + len {
            return Err(ConsoleError::FrameError("Incomplete payload".to_string()));
        }

        let payload = data[3..3 + len].to_vec();
        let received_crc = u16::from_le_bytes([data[3 + len], data[4 + len]]);
        let computed_crc = Self::compute_crc(&payload);

        if received_crc != computed_crc {
            return Err(ConsoleError::FrameError("CRC mismatch".to_string()));
        }

        Ok(Self { payload })
    }

    fn compute_crc(data: &[u8]) -> u16 {
        // Simple CRC16 computation using Fletcher's checksum variant
        let mut sum1: u16 = 0;
        let mut sum2: u16 = 0;

        for byte in data {
            sum1 = (sum1 + *byte as u16) % 255;
            sum2 = (sum2 + sum1) % 255;
        }

        ((sum2 as u16) << 8) | (sum1 as u16)
    }
}

pub struct UsbTunnel {
    #[allow(dead_code)]
    device_path: String,
    buffer: Arc<Mutex<Vec<u8>>>,
}

impl UsbTunnel {
    pub fn new(device_path: &str) -> Self {
        Self {
            device_path: device_path.to_string(),
            buffer: Arc::new(Mutex::new(Vec::with_capacity(4096))),
        }
    }

    pub async fn open(&mut self) -> Result<(), ConsoleError> {
        // In a real implementation, this would open the serial port
        // For now, we just validate the path
        if self.device_path.is_empty() {
            return Err(ConsoleError::UsbError("Invalid device path".to_string()));
        }
        Ok(())
    }

    pub async fn read_frame(&self) -> Result<Vec<u8>, ConsoleError> {
        let buffer = self.buffer.lock().await;
        if buffer.is_empty() {
            Err(ConsoleError::UsbError("No data available".to_string()))
        } else {
            Ok(buffer.clone())
        }
    }

    pub async fn write_frame(&self, data: &[u8]) -> Result<(), ConsoleError> {
        let mut buffer = self.buffer.lock().await;
        buffer.clear();
        buffer.extend_from_slice(data);
        Ok(())
    }

    pub async fn close(&self) -> Result<(), ConsoleError> {
        let mut buffer = self.buffer.lock().await;
        buffer.clear();
        Ok(())
    }

    pub fn device_path(&self) -> &str {
        &self.device_path
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_frame_encode_decode() {
        let payload = vec![1, 2, 3, 4, 5];
        let frame = Frame::new(payload.clone());
        let encoded = frame.encode().unwrap();

        assert_eq!(encoded[0], START_BYTE);
        assert!(encoded.len() > 5);

        let decoded = Frame::decode(&encoded).unwrap();
        assert_eq!(decoded.payload, payload);
    }

    #[test]
    fn test_frame_encode() {
        let frame = Frame::new(vec![0xAA, 0xBB]);
        let encoded = frame.encode().unwrap();
        assert_eq!(encoded[0], START_BYTE);
        assert_eq!(encoded[1], 0x02); // length low byte
        assert_eq!(encoded[2], 0x00); // length high byte
    }

    #[test]
    fn test_frame_decode_invalid_start() {
        let data = vec![0x00, 0x00, 0x00];
        let result = Frame::decode(&data);
        assert!(result.is_err());
    }

    #[test]
    fn test_frame_decode_short() {
        let data = vec![START_BYTE, 0x00];
        let result = Frame::decode(&data);
        assert!(result.is_err());
    }

    #[test]
    fn test_frame_crc_mismatch() {
        let payload = vec![1, 2, 3, 4];
        let mut encoded = vec![START_BYTE, 0x04, 0x00];
        encoded.extend_from_slice(&payload);
        encoded.extend_from_slice(&[0xFF, 0xFF]); // Invalid CRC

        let result = Frame::decode(&encoded);
        assert!(result.is_err());
    }

    #[tokio::test]
    async fn test_usb_tunnel_create() {
        let tunnel = UsbTunnel::new("/dev/ttyUSB0");
        assert_eq!(tunnel.device_path(), "/dev/ttyUSB0");
    }

    #[tokio::test]
    async fn test_usb_tunnel_open_valid_path() {
        let mut tunnel = UsbTunnel::new("/dev/ttyUSB0");
        assert!(tunnel.open().await.is_ok());
    }

    #[tokio::test]
    async fn test_usb_tunnel_open_invalid_path() {
        let mut tunnel = UsbTunnel::new("");
        assert!(tunnel.open().await.is_err());
    }

    #[tokio::test]
    async fn test_usb_tunnel_write_frame() {
        let tunnel = UsbTunnel::new("/dev/ttyUSB0");
        let data = b"test data";
        assert!(tunnel.write_frame(data).await.is_ok());
    }

    #[tokio::test]
    async fn test_usb_tunnel_read_empty() {
        let tunnel = UsbTunnel::new("/dev/ttyUSB0");
        let result = tunnel.read_frame().await;
        assert!(result.is_err());
    }

    #[tokio::test]
    async fn test_usb_tunnel_write_read() {
        let tunnel = UsbTunnel::new("/dev/ttyUSB0");
        let data = b"hello world";
        tunnel.write_frame(data).await.unwrap();

        let read_data = tunnel.read_frame().await.unwrap();
        assert_eq!(read_data, data);
    }

    #[tokio::test]
    async fn test_usb_tunnel_close() {
        let tunnel = UsbTunnel::new("/dev/ttyUSB0");
        tunnel.write_frame(b"data").await.unwrap();
        assert!(tunnel.close().await.is_ok());
        assert!(tunnel.read_frame().await.is_err());
    }

    #[test]
    fn test_frame_encode_empty() {
        let frame = Frame::new(vec![]);
        let encoded = frame.encode().unwrap();
        assert_eq!(encoded[0], START_BYTE);
        assert_eq!(encoded[1], 0x00);
        assert_eq!(encoded[2], 0x00);
    }

    #[test]
    fn test_frame_large_payload() {
        let payload = vec![0x42; 1000];
        let frame = Frame::new(payload.clone());
        let encoded = frame.encode().unwrap();

        let decoded = Frame::decode(&encoded).unwrap();
        assert_eq!(decoded.payload, payload);
    }
}
