const { createProxyMiddleware } = require("http-proxy-middleware");

module.exports = function (app) {
  const apiProxy = createProxyMiddleware("/api", {
    target: "http://localhost:8000",
    changeOrigin: true,
    ws: true,
    logLevel: "warn",
  });
  app.use(apiProxy);
};
