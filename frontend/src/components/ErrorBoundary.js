import React from "react";

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  componentDidCatch(error, info) {
    console.error("ErrorBoundary caught:", error, info);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary-page">
          <div className="error-boundary-card">
            <div style={{ fontSize: "3.5rem", marginBottom: "1rem" }}>⚠️</div>
            <h1>Bir Hata Oluştu</h1>
            <p>Beklenmeyen bir sorun meydana geldi. Lütfen sayfayı yenileyin.</p>
            <p className="error-detail">{this.state.error?.message}</p>
            <button className="btn-primary" onClick={() => { this.setState({ hasError: false }); window.location.href = "/dashboard"; }}>
              Ana Sayfaya Dön
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
