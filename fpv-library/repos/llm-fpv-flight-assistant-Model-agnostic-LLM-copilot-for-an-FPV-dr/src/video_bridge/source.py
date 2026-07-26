from video_bridge.frames import encode_jpeg


def on_image(msg, buffer, quality: int = 80, channels: int = 3) -> None:
    """Convert one gz Image message to JPEG and store it. Pure of gz imports."""
    # TODO(spike): gz Image may use a row stride (msg.step != width*channels); if the spike-confirmed topic reports padded rows, strip per-row padding before encoding.
    jpeg = encode_jpeg(bytes(msg.data), width=msg.width, height=msg.height,
                       channels=channels, quality=quality)
    buffer.set(jpeg)


def subscribe(topic: str, buffer, quality: int, channels: int):
    """Subscribe to a gz camera topic; returns the gz Node (keep it alive).

    Imports gz bindings lazily so the rest of the package is testable without them.
    """
    from gz.transport13 import Node
    from gz.msgs10.image_pb2 import Image

    node = Node()
    node.subscribe(Image, topic, lambda m: on_image(m, buffer, quality, channels))
    return node
