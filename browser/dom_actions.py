"""
Semantic DOM JavaScript payloads for Chromium CDP interaction on Nexus Mods.
Supports modern Web Components and Shadow DOM (e.g. <mod-download-modal>, <mod-file-download>).
Implements official flow detection without bypassing restrictions or skipping countdowns.
"""


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
    """Locates and clicks the 'Manual' or 'Manual Download' button across standard and Shadow DOM."""
    file_id_filter = f'"{file_id}"' if file_id else "null"
    return f"""
    (() => {{
        const targetFileId = {file_id_filter};

        function findInAllRoots(root, matcher) {{{{
            const queue = [root];
            while (queue.length > 0) {{{{
                const current = queue.shift();
                try {{{{
                    const elements = current.querySelectorAll("*");
                    for (const el of elements) {{{{
                        const match = matcher(el);
                        if (match) return match;
                        if (el.shadowRoot) {{{{
                            queue.push(el.shadowRoot);
                        }}}}
                    }}}}
                }}}} catch (e) {{{{}}}}
            }}}}
            return null;
        }}}}

        // 1. Requirements modal already open: click "Manual download" button
        let target = findInAllRoots(document, el => {{{{
            if (el.tagName === "BUTTON" || el.tagName === "A") {{{{
                const text = (el.textContent || "").trim().toLowerCase();
                if (text === "manual download") {{{{
                    return el;
                }}}}
            }}}}
            return null;
        }}}});

        // 2. Direct file ID match (e.g. data-file-id or inside <mod-download-modal>)
        if (!target && targetFileId) {{{{
            target = findInAllRoots(document, el => {{{{
                const href = el.getAttribute("href") || "";
                const dataId = el.getAttribute("data-file-id") || "";
                const fileAttr = el.getAttribute("file") || "";
                if (href.includes(`file_id=${{targetFileId}}`) || dataId === String(targetFileId) || fileAttr.includes(String(targetFileId))) {{{{
                    if (el.shadowRoot) {{{{
                        const subBtn = Array.from(el.shadowRoot.querySelectorAll("button, a")).find(b => (b.textContent||"").toLowerCase().includes("manual"));
                        if (subBtn) return subBtn;
                    }}}}
                    if (el.tagName === "BUTTON" || el.tagName === "A") return el;
                }}}}
                return null;
            }}}});
        }}}}

        // 3. General "Manual" or "Manual Download" button in document or shadow roots
        if (!target) {{{{
            target = findInAllRoots(document, el => {{{{
                if (el.tagName === "BUTTON" || el.tagName === "A" || el.getAttribute("role") === "button") {{{{
                    const text = (el.textContent || "").trim().toLowerCase();
                    if (text === "manual" || text === "manual download" || text.includes("manual download")) {{{{
                        return el;
                    }}}}
                }}}}
                return null;
            }}}});
        }}}}

        if (target) {{{{
            target.click();
            return {{{{ clicked: true, target: target.tagName, text: (target.textContent || "").trim() }}}};
        }}}}

        return {{{{ clicked: false, error: "MANUAL_DOWNLOAD_NOT_FOUND" }}}};
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
