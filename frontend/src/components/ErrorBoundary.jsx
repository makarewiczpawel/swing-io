import { Component } from "react";

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("UI crash:", error, info);
  }

  reset = () => this.setState({ error: null });

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div style={{
        padding: 24, margin: 24, border: "1px solid #ef4444",
        borderRadius: 8, background: "#1e1015", color: "#fca5a5",
        fontFamily: "system-ui, sans-serif",
      }}>
        <h2 style={{ margin: 0, fontSize: 18 }}>Coś poszło nie tak</h2>
        <p style={{ marginTop: 8, fontSize: 13, color: "#94a3b8" }}>
          {this.state.error.message || String(this.state.error)}
        </p>
        <button onClick={this.reset} style={{
          marginTop: 12, padding: "6px 14px", borderRadius: 6,
          border: "1px solid #ef4444", background: "transparent",
          color: "#fca5a5", cursor: "pointer",
        }}>
          Spróbuj ponownie
        </button>
      </div>
    );
  }
}
