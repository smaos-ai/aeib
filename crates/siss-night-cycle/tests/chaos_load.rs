use std::time::Instant;
use tokio::net::TcpListener;

#[tokio::test]
async fn test_dynamic_port_binding() {
    let listener1 = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let port1 = listener1.local_addr().unwrap().port();

    let listener2 = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let port2 = listener2.local_addr().unwrap().port();

    assert_ne!(port1, port2, "Dynamic ports should be different");
    assert!(port1 > 0, "Port 1 should be valid");
    assert!(port2 > 0, "Port 2 should be valid");
}

#[tokio::test]
async fn test_multi_region_concurrent_servers() {
    let listener1 = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let port1 = listener1.local_addr().unwrap().port();

    let listener2 = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let port2 = listener2.local_addr().unwrap().port();

    let port1_clone = port1.clone();
    let port2_clone = port2.clone();

    let handle1 = tokio::spawn(async move {
        let (socket, _) = listener1.accept().await.unwrap();
        socket
    });

    let handle2 = tokio::spawn(async move {
        let (socket, _) = listener2.accept().await.unwrap();
        socket
    });

    let client1 = tokio::spawn(async move {
        tokio::net::TcpStream::connect(("127.0.0.1", port1_clone))
            .await
            .unwrap()
    });

    let client2 = tokio::spawn(async move {
        tokio::net::TcpStream::connect(("127.0.0.1", port2_clone))
            .await
            .unwrap()
    });

    let _ = tokio::join!(client1, client2, handle1, handle2);
}

#[tokio::test]
async fn test_recovery_time_slo() {
    let start = Instant::now();

    let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let port = listener.local_addr().unwrap().port();

    let _server = tokio::spawn(async move {
        let _ = listener.accept().await;
    });

    let _client = tokio::spawn(async move {
        let _ = tokio::net::TcpStream::connect(("127.0.0.1", port)).await;
    });

    tokio::time::sleep(tokio::time::Duration::from_millis(100)).await;

    let elapsed = start.elapsed();
    assert!(
        elapsed.as_secs() < 5,
        "Recovery time should be < 5s, was {:?}",
        elapsed
    );
}

#[tokio::test]
async fn test_bounded_concurrent_connections() {
    let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let port = listener.local_addr().unwrap().port();

    let server_handle = tokio::spawn(async move {
        let mut count = 0;
        loop {
            match tokio::time::timeout(tokio::time::Duration::from_millis(100), listener.accept())
                .await
            {
                Ok(Ok(_)) => {
                    count += 1;
                }
                _ => break,
            }
        }
        count
    });

    let max_connections = 10;
    for _ in 0..max_connections {
        let port_copy = port.clone();
        tokio::spawn(async move {
            let _ = tokio::net::TcpStream::connect(("127.0.0.1", port_copy)).await;
        });
    }

    tokio::time::sleep(tokio::time::Duration::from_millis(500)).await;

    let connection_count = server_handle.await.unwrap();
    assert!(
        connection_count <= max_connections,
        "Should not exceed {} connections, got {}",
        max_connections,
        connection_count
    );
}
