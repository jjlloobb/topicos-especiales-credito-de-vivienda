// Un bus de `BroadcastChannel` falso y sincrono (solo pruebas): cada canal recibe lo que publican los DEMAS, como el real.
import type { ChannelLike } from "../../src/inactivity/monitor";

export class Bus {
  readonly posted: unknown[] = [];
  private readonly channels = new Set<FakeChannel>();

  channel(): FakeChannel {
    const created = new FakeChannel(this);
    this.channels.add(created);
    return created;
  }

  publish(from: FakeChannel, message: unknown): void {
    this.posted.push(message);
    for (const other of this.channels) if (other !== from && !other.closed) other.deliver(message);
  }
}

export class FakeChannel implements ChannelLike {
  closed = false;
  private listeners = new Set<(event: { readonly data: unknown }) => void>();

  constructor(private readonly bus: Bus) {}

  postMessage(message: { readonly type: "activity" | "logout" }): void {
    this.bus.publish(this, message);
  }
  addEventListener(_type: "message", listener: (event: { readonly data: unknown }) => void): void {
    this.listeners.add(listener);
  }
  removeEventListener(_type: "message", listener: (event: { readonly data: unknown }) => void): void {
    this.listeners.delete(listener);
  }
  close(): void {
    this.closed = true;
  }
  deliver(data: unknown): void {
    for (const listener of [...this.listeners]) listener({ data });
  }
}
