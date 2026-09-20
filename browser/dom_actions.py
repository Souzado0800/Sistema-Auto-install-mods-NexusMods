"""
Semantic DOM JavaScript payloads for Chromium CDP interaction on Nexus Mods.
Supports modern Web Components and Shadow DOM (e.g. <mod-download-modal>, <mod-file-download>).
Implements official flow detection without bypassing restrictions or skipping countdowns.
"""

import json


def get_check_challenges_js() -> str:
    """Detects Cloudflare challenges, CAPTCHAs, or login requirements across main DOM and Shadow DOM."""
    return """
    (() => {
        function findInAllRoots(root, matcher) {
            const queue = [root];
            while (queue.length > 0) {
                const current = queue.shift();
                try {
                    const elements = current.querySelectorAll("*");
                    for (const el of elements) {
                        const match = matcher(el);
                        if (match) return match;
                        if (el.shadowRoot) {
                            queue.push(el.shadowRoot);
                        }
                    }
                } catch (e) {}
            }
            return null;
        }

        // 1. Cloudflare Turnstile / Managed Challenge
        const cfMatch = findInAllRoots(document, el => {
            const id = el.id || "";
            const cls = (typeof el.className === "string") ? el.className : "";
            const src = el.getAttribute("src") || "";
            if (id === "challenge-stage" || id === "cf-please-wait" || id === "challenge-running" || src.includes("challenges.cloudflare")) {
                if (el.offsetParent !== null) {
                    return { challenge: true, type: "CLOUDFLARE_CHALLENGE", details: "Cloudflare verification in progress" };
                }
            }
            return null;
        });
        if (cfMatch) return cfMatch;

        // 2. CAPTCHA (reCAPTCHA, hCaptcha)
        const captchaMatch = findInAllRoots(document, el => {
            const id = el.id || "";
            const cls = (typeof el.className === "string") ? el.className : "";
            const src = el.getAttribute("src") || "";
            if (cls.includes("g-recaptcha") || id === "recaptcha" || cls.includes("h-captcha") || src.includes("recaptcha")) {
                if (el.offsetParent !== null) {
                    return { challenge: true, type: "CAPTCHA", details: "CAPTCHA verification required" };
                }
            }
            return null;
        });
        if (captchaMatch) return captchaMatch;

        // 3. Login prompt / session expiry
        const loginMatch = findInAllRoots(document, el => {
            const id = el.id || "";
            const cls = (typeof el.className === "string") ? el.className : "";
            const action = el.getAttribute("action") || "";
            if (action.includes("/login") || cls.includes("btn-login") || id === "login-dialog") {
                if (el.offsetParent !== null) {
                    return { challenge: true, type: "LOGIN_REQUIRED", details: "User session not authenticated on page" };
                }
            }
            return null;
        });
        if (loginMatch) return loginMatch;

        return { challenge: false };
    })()
    """


def get_click_manual_download_js(file_id: int | None = None) -> str:
    """
    Locates and clicks the 'Manual' or 'Manual Download' button across standard and Shadow DOM.
    Prioritizes:
    1. Active Requirements modal confirmation button
    2. 'Main files' section (#file-container-main-files, first file or matching file_id)
    3. Direct file ID match across the document
    4. Top header mod-download-modal (placement='mod_page')
    5. General fallback across all DOM roots
    """
    target_id_json = json.dumps(str(file_id)) if file_id else "null"
    return f"""
    (() => {{
        const targetFileId = {target_id_json};

        function findInAllRoots(root, matcher) {{
            const queue = [root];
            while (queue.length > 0) {{
                const current = queue.shift();
                try {{
                    const elements = current.querySelectorAll("*");
                    for (const el of elements) {{
                        const match = matcher(el);
                        if (match) return match;
                        if (el.shadowRoot) {{
                            queue.push(el.shadowRoot);
                        }}
                    }}
                }} catch (e) {{}}
            }}
            return null;
        }}

        // 1. Requirements modal already open: click "Manual download" button
        const reqModalButton = findInAllRoots(document, el => {{
            if (el.tagName === "A" || el.tagName === "BUTTON") {{
                const cls = (typeof el.className === "string") ? el.className : "";
                const text = (el.textContent || "").trim().toLowerCase();
                if (cls.includes("nxm-button-secondary-filled-strong") && text.includes("manual")) {{
                    return el;
                }}
                const parentDialog = el.closest && el.closest("dialog, .popup, .mfp-content, [role='dialog'], .modal");
                if (parentDialog && (text === "manual download" || text === "download" || text.includes("manual download"))) {{
                    return el;
                }}
            }}
            return null;
        }});

        if (reqModalButton) {{
            reqModalButton.click();
            return {{ clicked: true, stage: "REQUIREMENTS_MODAL", target: reqModalButton.tagName, text: (reqModalButton.textContent || "").trim() }};
        }}

        // 2. MAIN FILES SECTION (Primary target when tab is on ?tab=files)
        let mainFilesSection = document.getElementById("file-container-main-files");
        if (!mainFilesSection) {{
            const heading = Array.from(document.querySelectorAll("h1, h2, h3, h4, dt, .file-category-header, .accordion-name")).find(el => {{
                const t = (el.textContent || "").trim().toLowerCase();
                return t === "main files" || t.startsWith("main files");
            }});
            if (heading) {{
                mainFilesSection = heading.closest(".files-tabs, .tabbed-section, .tab-files, .accordionitems") || heading.parentElement;
            }}
        }}

        if (mainFilesSection) {{
            // Expand any collapsed accordion item under Main files if present
            const closedHeaders = mainFilesSection.querySelectorAll("dt.file-expander-header:not(.accopen)");
            for (const h of closedHeaders) {{
                try {{ h.click(); }} catch (e) {{}}
            }}

            // Look for mod-download-modal inside Main files
            let mainModal = null;
            if (targetFileId) {{
                mainModal = Array.from(mainFilesSection.querySelectorAll("mod-download-modal")).find(m => {{
                    const fileAttr = m.getAttribute("file") || "";
                    const dataId = m.getAttribute("data-file-id") || m.getAttribute("data-id") || "";
                    return fileAttr.includes(String(targetFileId)) || dataId === String(targetFileId);
                }});
            }}
            if (!mainModal) {{
                mainModal = mainFilesSection.querySelector("mod-download-modal");
            }}

            if (mainModal && mainModal.shadowRoot) {{
                const btn = Array.from(mainModal.shadowRoot.querySelectorAll("button, a")).find(b => {{
                    const t = (b.textContent || "").trim().toLowerCase();
                    return t.includes("manual");
                }});
                if (btn) {{
                    btn.click();
                    return {{ clicked: true, stage: "MAIN_FILES_SHADOW_MODAL", target: btn.tagName, text: (btn.textContent || "").trim() }};
                }}
            }}

            // Standard button inside Main files
            const stdBtn = Array.from(mainFilesSection.querySelectorAll("button, a")).find(b => {{
                const t = (b.textContent || "").trim().toLowerCase();
                return t === "manual download" || t === "manual" || t.includes("manual download");
            }});
            if (stdBtn) {{
                stdBtn.click();
                return {{ clicked: true, stage: "MAIN_FILES_STANDARD", target: stdBtn.tagName, text: (stdBtn.textContent || "").trim() }};
            }}
        }}

        // 3. Direct file ID match across the entire document / shadow roots
        if (targetFileId) {{
            const fileMatch = findInAllRoots(document, el => {{
                const href = el.getAttribute("href") || "";
                const dataId = el.getAttribute("data-file-id") || el.getAttribute("data-id") || "";
                const fileAttr = el.getAttribute("file") || "";
                if (href.includes(`file_id=${{targetFileId}}`) || dataId === String(targetFileId) || fileAttr.includes(String(targetFileId))) {{
                    if (el.shadowRoot) {{
                        const subBtn = Array.from(el.shadowRoot.querySelectorAll("button, a")).find(b => {{
                            return (b.textContent || "").toLowerCase().includes("manual");
                        }});
                        if (subBtn) return subBtn;
                    }}
                    if (el.tagName === "BUTTON" || el.tagName === "A") return el;
                }}
                return null;
            }});
            if (fileMatch) {{
                fileMatch.click();
                return {{ clicked: true, stage: "FILE_ID_MATCH", target: fileMatch.tagName, text: (fileMatch.textContent || "").trim() }};
            }}
        }}

        // 4. Header mod-download-modal (placement="mod_page")
        const headerModal = document.querySelector("mod-download-modal[placement='mod_page'], mod-download-modal");
        if (headerModal && headerModal.shadowRoot) {{
            const btn = Array.from(headerModal.shadowRoot.querySelectorAll("button, a")).find(b => {{
                const t = (b.textContent || "").trim().toLowerCase();
                return t === "manual" || t.includes("manual");
            }});
            if (btn) {{
                btn.click();
                return {{ clicked: true, stage: "HEADER_MODAL", target: btn.tagName, text: (btn.textContent || "").trim() }};
            }}
        }}

        // 5. General "Manual" or "Manual Download" button in document or shadow roots
        const generalTarget = findInAllRoots(document, el => {{
            if (el.tagName === "BUTTON" || el.tagName === "A" || el.getAttribute("role") === "button") {{
                const text = (el.textContent || "").trim().toLowerCase();
                if (text === "manual" || text === "manual download" || text.includes("manual download")) {{
                    return el;
                }}
            }}
            return null;
        }});

        if (generalTarget) {{
            generalTarget.click();
            return {{ clicked: true, stage: "GENERAL_FALLBACK", target: generalTarget.tagName, text: (generalTarget.textContent || "").trim() }};
        }}

        return {{ clicked: false, error: "MANUAL_DOWNLOAD_NOT_FOUND" }};
    }})()
    """


def get_click_slow_download_js() -> str:
    """Locates and clicks the official 'Slow Download' button across standard and Shadow DOM."""
    return """
    (() => {
        function findInAllRoots(root, matcher) {
            const queue = [root];
            while (queue.length > 0) {
                const current = queue.shift();
                try {
                    const elements = current.querySelectorAll("*");
                    for (const el of elements) {
                        const match = matcher(el);
                        if (match) return match;
                        if (el.shadowRoot) {
                            queue.push(el.shadowRoot);
                        }
                    }
                } catch (e) {}
            }
            return null;
        }

        // 1. Official Nexus Mods Slow Download button ID or selector (#slowDownloadButton)
        let target = findInAllRoots(document, el => {
            if (el.id === "slowDownloadButton" || (el.matches && el.matches("#slowDownloadButton")) || el.getAttribute("data-download-type") === "slow") {
                return el;
            }
            return null;
        });

        // 2. Search by semantic text across all elements and shadow roots (e.g. <mod-file-download>)
        if (!target) {
            target = findInAllRoots(document, el => {
                if (el.tagName === "BUTTON" || el.tagName === "A" || el.getAttribute("role") === "button") {
                    const text = (el.textContent || "").trim().toLowerCase();
                    if (text === "slow download" || text.includes("slow download")) {
                        return el;
                    }
                }
                return null;
            });
        }

        if (target) {
            target.click();
            return { clicked: true, target: target.tagName, text: (target.textContent || "").trim() };
        }

        return { clicked: false, error: "SLOW_DOWNLOAD_NOT_FOUND" };
    })()
    """


def get_check_countdown_js() -> str:
    """Inspects the page for official Nexus Mods download countdown without modifying it."""
    return r"""
    (() => {
        function findInAllRoots(root, matcher) {
            const queue = [root];
            while (queue.length > 0) {
                const current = queue.shift();
                try {
                    const elements = current.querySelectorAll("*");
                    for (const el of elements) {
                        const match = matcher(el);
                        if (match) return match;
                        if (el.shadowRoot) {
                            queue.push(el.shadowRoot);
                        }
                    }
                } catch (e) {}
            }
            return null;
        }

        const countdown = findInAllRoots(document, el => {
            const text = (el.textContent || "").trim();
            const m = text.match(/download will start in (\d+) second/i);
            if (m) {
                return { countdown: true, seconds_left: parseInt(m[1], 10) };
            }
            if (el.id === "countdown" || (el.matches && el.matches("#countdown")) || (el.classList && el.classList.contains("countdown"))) {
                const val = parseInt(el.textContent || "0", 10);
                return { countdown: true, seconds_left: isNaN(val) ? 5 : val };
            }
            return null;
        });

        return countdown || { countdown: false };
    })()
    """
