import { Component, type ReactNode } from "react";

/**
 * A component failure must never black-screen the workstation. Persisted
 * data lives server-side, so recovery is always safe: reset to the
 * landing view and let the technician reopen from History.
 */
export class ErrorBoundary extends Component<
  { children: ReactNode; onReset?: () => void },
  { failed: boolean; detail: string }
> {
  state = { failed: false, detail: "" };

  static getDerivedStateFromError(error: unknown): { failed: boolean; detail: string } {
    return {
      failed: true,
      detail: error instanceof Error ? error.message : String(error),
    };
  }

  private recover = () => {
    this.setState({ failed: false, detail: "" });
    this.props.onReset?.();
  };

  render(): ReactNode {
    if (!this.state.failed) return this.props.children;
    return (
      <section className="card boundary" role="alert">
        <h2>Something in this view broke</h2>
        <p>
          FieldRook hit a display error instead of your data. Investigations,
          notes, and knowledge are stored server-side and are unaffected.
        </p>
        {this.state.detail && (
          <p className="muted mono">{this.state.detail.slice(0, 300)}</p>
        )}
        <div className="controls">
          <button type="button" className="button" onClick={this.recover}>
            Back to a clean view
          </button>
        </div>
      </section>
    );
  }
}
