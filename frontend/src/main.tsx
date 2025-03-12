import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

try {
  const rootElement = document.getElementById("root");
  
  if (rootElement) {
    const root = ReactDOM.createRoot(rootElement);
    root.render(
      <React.StrictMode>
        <App />
      </React.StrictMode>
    );
    console.log("App rendered successfully");
    
    // Hide the fallback content directly after rendering
    const fallback = document.getElementById("fallback");
    if (fallback) {
      fallback.style.display = "none";
      console.log("React initialized, hiding fallback content");
    }
  } else {
    console.error("Could not find root element");
  }
} catch (error) {
  console.error("Error during app initialization:", error);
  document.body.innerHTML = `
    <div style="padding: 20px; color: red; font-family: sans-serif;">
      <h1>Application Error</h1>
      <p>There was an error loading the application:</p>
      <pre>${error instanceof Error ? error.message : String(error)}</pre>
    </div>
  `;
}