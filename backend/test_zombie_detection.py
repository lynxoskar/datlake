#!/usr/bin/env python3
"""
Test script for SSE zombie detection
Demonstrates various zombie scenarios and detection capabilities
"""

import asyncio
import aiohttp
import time
import json
from typing import List, Dict, Any


class SSETestClient:
    """Test SSE client that can simulate zombie behavior"""
    
    def __init__(self, client_id: str, simulate_zombie: str = None):
        self.client_id = client_id
        self.simulate_zombie = simulate_zombie  # 'no_pong', 'disconnect', 'slow_response'
        self.session = None
        self.connection = None
        self.running = False
        self.events_received = 0
        self.pings_received = 0
        self.pongs_sent = 0
    
    async def connect(self, base_url: str = "http://localhost:8000"):
        """Connect to SSE stream"""
        self.session = aiohttp.ClientSession()
        
        try:
            self.connection = await self.session.get(
                f"{base_url}/events/stream?events=ping,heartbeat,system_metric",
                headers={'Accept': 'text/event-stream'}
            )
            
            print(f"[{self.client_id}] Connected to SSE stream")
            self.running = True
            
            # Start listening for events
            await self._listen_for_events(base_url)
            
        except Exception as e:
            print(f"[{self.client_id}] Connection failed: {e}")
            await self.disconnect()
    
    async def _listen_for_events(self, base_url: str):
        """Listen for SSE events"""
        try:
            async for line in self.connection.content:
                line = line.decode('utf-8').strip()
                
                if line.startswith('event: '):
                    event_type = line.split(': ', 1)[1]
                elif line.startswith('data: '):
                    data_str = line.split(': ', 1)[1]
                    
                    try:
                        data = json.loads(data_str)
                        self.events_received += 1
                        
                        # Handle ping events
                        if event_type == 'ping':
                            await self._handle_ping(data, base_url)
                        
                        print(f"[{self.client_id}] Received {event_type}: events={self.events_received}, pings={self.pings_received}, pongs={self.pongs_sent}")
                        
                    except json.JSONDecodeError:
                        pass
                
                # Simulate zombie behavior
                if self.simulate_zombie == 'disconnect' and self.events_received >= 3:
                    print(f"[{self.client_id}] Simulating unexpected disconnect")
                    await self.session.close()
                    return
                
        except Exception as e:
            print(f"[{self.client_id}] Error listening for events: {e}")
        finally:
            await self.disconnect()
    
    async def _handle_ping(self, data: Dict[str, Any], base_url: str):
        """Handle ping event"""
        self.pings_received += 1
        
        ping_data = data.get('data', {})
        ping_id = ping_data.get('ping_id')
        expected_pong = ping_data.get('expected_pong', False)
        
        if expected_pong and ping_id:
            if self.simulate_zombie == 'no_pong':
                print(f"[{self.client_id}] Ignoring ping (simulating no pong)")
                return
            
            if self.simulate_zombie == 'slow_response':
                print(f"[{self.client_id}] Slow response to ping")
                await asyncio.sleep(30)  # Delayed response
            
            # Send pong response
            try:
                async with self.session.post(
                    f"{base_url}/events/pong",
                    json={"client_id": self.client_id, "ping_id": ping_id}
                ) as response:
                    if response.status == 200:
                        self.pongs_sent += 1
                        print(f"[{self.client_id}] Sent pong for ping {ping_id}")
                    else:
                        print(f"[{self.client_id}] Failed to send pong: {response.status}")
            except Exception as e:
                print(f"[{self.client_id}] Error sending pong: {e}")
    
    async def disconnect(self):
        """Disconnect from SSE stream"""
        self.running = False
        if self.connection:
            self.connection.close()
        if self.session:
            await self.session.close()
        print(f"[{self.client_id}] Disconnected")


async def get_sse_stats(base_url: str = "http://localhost:8000") -> Dict[str, Any]:
    """Get SSE connection statistics"""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{base_url}/events/stats") as response:
            return await response.json()


async def get_zombie_stats(base_url: str = "http://localhost:8000") -> Dict[str, Any]:
    """Get zombie detection statistics"""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{base_url}/events/zombies") as response:
            return await response.json()


async def cleanup_zombies(base_url: str = "http://localhost:8000") -> Dict[str, Any]:
    """Force cleanup of zombie clients"""
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{base_url}/events/zombies/cleanup") as response:
            return await response.json()


async def send_test_event(base_url: str = "http://localhost:8000"):
    """Send a test event to trigger activity"""
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{base_url}/events/broadcast",
            json={
                "event_type": "system_metric",
                "data": {
                    "metric_type": "zombie_test",
                    "value": time.time(),
                    "metadata": {"source": "zombie_test_script"}
                }
            }
        ) as response:
            return await response.json()


async def run_zombie_detection_test():
    """Run comprehensive zombie detection test"""
    base_url = "http://localhost:8000"
    
    print("🧟 Starting Zombie Detection Test")
    print("=" * 50)
    
    # Create different types of clients
    clients = [
        SSETestClient("healthy-client", None),
        SSETestClient("no-pong-zombie", "no_pong"),
        SSETestClient("disconnect-zombie", "disconnect"),
        SSETestClient("slow-response-zombie", "slow_response"),
    ]
    
    # Start all clients
    print("\n1. Connecting test clients...")
    client_tasks = []
    for client in clients:
        task = asyncio.create_task(client.connect(base_url))
        client_tasks.append(task)
    
    # Wait for connections to establish
    await asyncio.sleep(2)
    
    # Send some test events
    print("\n2. Sending test events...")
    for i in range(5):
        await send_test_event(base_url)
        await asyncio.sleep(1)
    
    # Check initial stats
    print("\n3. Initial connection stats:")
    stats = await get_sse_stats(base_url)
    print(f"   Connected clients: {stats.get('connected_clients', 0)}")
    print(f"   Healthy clients: {stats.get('healthy_clients', 0)}")
    print(f"   Zombie clients: {stats.get('zombie_clients', 0)}")
    
    # Wait for zombie detection to kick in
    print("\n4. Waiting for zombie detection (60 seconds)...")
    for i in range(12):  # 60 seconds
        await asyncio.sleep(5)
        
        # Send periodic test events
        if i % 3 == 0:
            await send_test_event(base_url)
        
        print(f"   Progress: {(i+1)*5}/60 seconds")
    
    # Check stats after zombie detection
    print("\n5. Stats after zombie detection:")
    stats = await get_sse_stats(base_url)
    print(f"   Connected clients: {stats.get('connected_clients', 0)}")
    print(f"   Healthy clients: {stats.get('healthy_clients', 0)}")
    print(f"   Zombie clients: {stats.get('zombie_clients', 0)}")
    
    # Get detailed zombie stats
    print("\n6. Detailed zombie statistics:")
    zombie_stats = await get_zombie_stats(base_url)
    print(f"   Current zombies: {zombie_stats.get('current_zombies', 0)}")
    print(f"   Total detected: {zombie_stats.get('total_detected', 0)}")
    print(f"   Detection reasons: {zombie_stats.get('detection_reasons', {})}")
    
    # Show individual client details
    if stats.get('clients'):
        print("\n7. Individual client details:")
        for client in stats['clients']:
            status = "🧟 ZOMBIE" if client['is_zombie'] else "✅ HEALTHY"
            print(f"   {client['client_id'][:8]}... - {status}")
            print(f"      Duration: {client['connected_duration']:.1f}s")
            print(f"      Pings: {client['ping_count']} (missed: {client['missed_pings']})")
            print(f"      Errors: {client['write_errors']} write, {client['queue_full_count']} queue")
    
    # Cleanup zombies
    print("\n8. Cleaning up zombie clients...")
    cleanup_result = await cleanup_zombies(base_url)
    print(f"   {cleanup_result.get('message', 'Cleanup completed')}")
    
    # Final stats
    print("\n9. Final stats after cleanup:")
    stats = await get_sse_stats(base_url)
    print(f"   Connected clients: {stats.get('connected_clients', 0)}")
    print(f"   Healthy clients: {stats.get('healthy_clients', 0)}")
    print(f"   Zombie clients: {stats.get('zombie_clients', 0)}")
    
    # Cancel remaining client tasks
    print("\n10. Cleaning up test...")
    for task in client_tasks:
        if not task.done():
            task.cancel()
    
    # Wait for tasks to complete
    await asyncio.gather(*client_tasks, return_exceptions=True)
    
    print("\n✅ Zombie Detection Test Complete!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(run_zombie_detection_test()) 