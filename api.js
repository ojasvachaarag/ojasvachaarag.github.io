// ============================================================================
// API Configuration
// ============================================================================
// Set your API Base URL, API Key, and route endpoints below when ready.
const API_CONFIG = {
    // Base URL for the backend API (e.g., "https://api.yourdomain.com" or "http://localhost:8000")
    baseURL: "",

    // API Key for authenticating requests (sent via X-API-Key and Authorization Bearer headers)
    apiKey: "",

    // Route for contact form submissions (to be configured later, e.g., "/api/v1/contact")
    contactRoute: ""
};

/**
 * Universal helper to make requests to the backend API.
 * Automatically resolves endpoints against API_CONFIG.baseURL and attaches auth headers.
 *
 * @param {string} endpoint - The API endpoint path (e.g. "/api/v1/contact") or a full URL
 * @param {RequestInit} [options={}] - Fetch configuration options (method, headers, body, etc.)
 * @returns {Promise<any>} Parsed response data
 */
async function apiRequest(endpoint, options = {}) {
    if (!API_CONFIG.baseURL) {
        throw new Error("API baseURL is not configured. Please set API_CONFIG.baseURL in api.js.");
    }

    const url = endpoint.startsWith("http://") || endpoint.startsWith("https://")
        ? endpoint
        : `${API_CONFIG.baseURL.replace(/\/+$/, "")}/${endpoint.replace(/^\/+/, "")}`;

    const headers = {
        "Content-Type": "application/json",
        ...(options.headers || {})
    };

    if (API_CONFIG.apiKey) {
        headers["X-API-Key"] = API_CONFIG.apiKey;
        headers["Authorization"] = `Bearer ${API_CONFIG.apiKey}`;
    }

    const response = await fetch(url, {
        ...options,
        headers
    });

    if (!response.ok) {
        let errorMessage = `API request failed with status ${response.status}`;
        try {
            const errorData = await response.json();
            if (errorData.message || errorData.detail) {
                errorMessage = errorData.message || errorData.detail;
            }
        } catch (_) {
            const errorText = await response.text();
            if (errorText) errorMessage = errorText;
        }
        throw new Error(errorMessage);
    }

    const text = await response.text();
    return text ? JSON.parse(text) : null;
}

/**
 * Contact form submit handler.
 * Gathers form data and dispatches to API_CONFIG.contactRoute once configured.
 */
function initContactForm() {
    const contactForm = document.getElementById("contact-form");
    if (!contactForm) return;

    contactForm.addEventListener("submit", async function (e) {
        e.preventDefault();

        const formData = {
            name: document.getElementById("name").value.trim(),
            email: document.getElementById("email").value.trim(),
            message: document.getElementById("message").value.trim()
        };

        // If the API endpoint or base URL is not configured yet
        if (!API_CONFIG.baseURL || !API_CONFIG.contactRoute) {
            console.log("Contact form submitted (waiting for API route configuration):", formData);
            alert("Thank you for your message! (The API route is currently being configured)");
            contactForm.reset();
            return;
        }

        try {
            await apiRequest(API_CONFIG.contactRoute, {
                method: "POST",
                body: JSON.stringify(formData)
            });

            alert("Message sent successfully!");
            contactForm.reset();
        } catch (error) {
            alert(`Error submitting form: ${error.message || "Please try again later."}`);
            console.error("Contact Form Error:", error);
        }
    });
}

// Initialize when the DOM is ready
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initContactForm);
} else {
    initContactForm();
}
