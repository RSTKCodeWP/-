using System.Net;
using System.Net.Sockets;

namespace ApexControl.Core.Services;

public sealed class UdpDroneConnection : IAsyncDisposable
{
    private readonly UdpClient udpClient;
    private readonly IPEndPoint remoteEndPoint;
    private CancellationTokenSource? cancellationTokenSource;

    public event EventHandler<byte[]>? BytesReceived;

    public bool IsRunning { get; private set; }

    public int ListenPort { get; }
    public string RemoteHost { get; }
    public int RemotePort { get; }

    public UdpDroneConnection(int listenPort = 14550, string remoteHost = "127.0.0.1", int remotePort = 14550)
    {
        ListenPort = listenPort;
        RemoteHost = remoteHost;
        RemotePort = remotePort;

        udpClient = new UdpClient(new IPEndPoint(IPAddress.Any, listenPort));
        remoteEndPoint = new IPEndPoint(IPAddress.Parse(remoteHost), remotePort);
    }

    public Task StartAsync(CancellationToken cancellationToken = default)
    {
        if (IsRunning) return Task.CompletedTask;

        IsRunning = true;
        cancellationTokenSource = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);

        _ = Task.Run(async () => await ReceiveLoopAsync(cancellationTokenSource.Token), cancellationTokenSource.Token);
        return Task.CompletedTask;
    }

    private async Task ReceiveLoopAsync(CancellationToken cancellationToken)
    {
        while (!cancellationToken.IsCancellationRequested)
        {
            try
            {
                var result = await udpClient.ReceiveAsync(cancellationToken);
                BytesReceived?.Invoke(this, result.Buffer);
            }
            catch (OperationCanceledException)
            {
                break;
            }
            catch
            {
                try
                {
                    await Task.Delay(300, cancellationToken);
                }
                catch (OperationCanceledException)
                {
                    break;
                }
            }
        }
    }

    public async Task SendAsync(byte[] data, CancellationToken cancellationToken = default)
    {
        cancellationToken.ThrowIfCancellationRequested();
        await udpClient.SendAsync(data, data.Length, remoteEndPoint);
    }

    public Task StopAsync()
    {
        if (!IsRunning) return Task.CompletedTask;

        IsRunning = false;
        cancellationTokenSource?.Cancel();
        cancellationTokenSource?.Dispose();
        cancellationTokenSource = null;

        return Task.CompletedTask;
    }

    public async ValueTask DisposeAsync()
    {
        await StopAsync();
        udpClient.Dispose();
    }
}
