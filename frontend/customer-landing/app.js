(() => {
  const form = document.getElementById("order-form");
  const messageBox = document.getElementById("form-messages");

  if (!form || !messageBox) {
    console.warn("Customer order form assets missing from the page.");
    return;
  }

  const submitButton = form.querySelector('[type="submit"]');
  if (!submitButton) {
    console.warn("Submit button missing from the order form.");
    return;
  }
  const API_ENDPOINT = "/api/orders";

  const setMessage = (text, variant = "success") => {
    messageBox.textContent = text;
    messageBox.classList.remove("alert--hidden", "alert--success", "alert--error");
    if (variant === "error") {
      messageBox.classList.add("alert--error");
    } else {
      messageBox.classList.add("alert--success");
    }
  };

  const clearMessage = () => {
    messageBox.textContent = "";
    messageBox.className = "alert alert--hidden";
  };

  const normalizeValue = (value) => {
    if (typeof value !== "string") return undefined;
    const trimmed = value.trim();
    return trimmed.length ? trimmed : undefined;
  };

  const normalizeDateTime = (value) => {
    if (!value) return undefined;
    try {
      const iso = new Date(value);
      if (Number.isNaN(iso.getTime())) {
        return undefined;
      }
      return iso.toISOString();
    } catch {
      return undefined;
    }
  };

  const toggleSubmitting = (isSubmitting) => {
    submitButton.disabled = isSubmitting;
    submitButton.dataset.loading = isSubmitting ? "true" : "false";
    submitButton.textContent = isSubmitting ? "Submitting…" : "Submit order";
  };

  const extractErrorMessage = (payload) => {
    if (!payload) return "We could not process your order. Please try again.";
    if (typeof payload.detail === "string") {
      return payload.detail;
    }
    if (Array.isArray(payload.detail)) {
      return payload.detail.map((entry) => entry.msg || JSON.stringify(entry)).join(", ");
    }
    if (payload.validation_errors && payload.validation_errors.length) {
      return payload.validation_errors.join(", ");
    }
    return "We could not process your order. Please try again.";
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    clearMessage();

    const formData = new FormData(form);
    const deliveryAddress = normalizeValue(formData.get("delivery_address"));
    if (!deliveryAddress) {
      setMessage("Delivery address is required.", "error");
      return;
    }

    const payload = {
      customer_name: normalizeValue(formData.get("customer_name")),
      customer_phone: normalizeValue(formData.get("customer_phone")),
      customer_email: normalizeValue(formData.get("customer_email")),
      delivery_address: deliveryAddress,
      delivery_time_window_start: normalizeDateTime(
        formData.get("delivery_time_window_start")
      ),
      delivery_time_window_end: normalizeDateTime(
        formData.get("delivery_time_window_end")
      ),
      description: normalizeValue(formData.get("description")),
      source: "customer_portal",
    };

    Object.keys(payload).forEach((key) => {
      if (payload[key] === undefined) {
        delete payload[key];
      }
    });

    try {
      toggleSubmitting(true);
      const response = await fetch(API_ENDPOINT, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify(payload),
      });

      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(extractErrorMessage(body));
      }

      const orderNumber = body.order_number || body.id || "your order";
      setMessage(`Thanks! We received ${orderNumber} and will dispatch shortly.`);
      form.reset();
      const firstField = form.querySelector("input, textarea, select");
      if (firstField) {
        firstField.focus();
      }
    } catch (error) {
      setMessage(error.message || "Something went wrong. Please try again.", "error");
    } finally {
      toggleSubmitting(false);
    }
  };

  form.addEventListener("submit", handleSubmit);

  const yearNode = document.getElementById("copyright-year");
  if (yearNode) {
    yearNode.textContent = String(new Date().getFullYear());
  }

  // Voice input functionality
  const voiceBtn = document.getElementById("voice-input-btn");
  const voiceStatus = document.getElementById("voice-status");

  if (voiceBtn && voiceStatus) {
    let mediaRecorder = null;
    let audioChunks = [];
    let isRecording = false;

    const updateVoiceStatus = (text, className = "") => {
      if (text) {
        voiceStatus.textContent = text;
        voiceStatus.className = `voice-status ${className}`;
        voiceStatus.classList.remove("voice-status--hidden");
      } else {
        voiceStatus.classList.add("voice-status--hidden");
      }
    };

    const convertISOToLocalDateTime = (isoString) => {
      if (!isoString) return "";
      try {
        const date = new Date(isoString);
        if (Number.isNaN(date.getTime())) return "";
        // Format as datetime-local input expects: YYYY-MM-DDTHH:MM
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, "0");
        const day = String(date.getDate()).padStart(2, "0");
        const hours = String(date.getHours()).padStart(2, "0");
        const minutes = String(date.getMinutes()).padStart(2, "0");
        return `${year}-${month}-${day}T${hours}:${minutes}`;
      } catch {
        return "";
      }
    };

    const populateFormFields = (parsedData) => {
      if (parsedData.customer_name) {
        const nameField = form.querySelector('[name="customer_name"]');
        if (nameField) nameField.value = parsedData.customer_name;
      }

      if (parsedData.customer_phone) {
        const phoneField = form.querySelector('[name="customer_phone"]');
        if (phoneField) phoneField.value = parsedData.customer_phone;
      }

      if (parsedData.customer_email) {
        const emailField = form.querySelector('[name="customer_email"]');
        if (emailField) emailField.value = parsedData.customer_email;
      }

      if (parsedData.delivery_address) {
        const addressField = form.querySelector('[name="delivery_address"]');
        if (addressField) addressField.value = parsedData.delivery_address;
      }

      if (parsedData.description) {
        const descField = form.querySelector('[name="description"]');
        if (descField) descField.value = parsedData.description;
      }

      if (parsedData.delivery_time_window_start) {
        const startField = form.querySelector('[name="delivery_time_window_start"]');
        if (startField) {
          const localDateTime = convertISOToLocalDateTime(parsedData.delivery_time_window_start);
          if (localDateTime) startField.value = localDateTime;
        }
      }

      if (parsedData.delivery_time_window_end) {
        const endField = form.querySelector('[name="delivery_time_window_end"]');
        if (endField) {
          const localDateTime = convertISOToLocalDateTime(parsedData.delivery_time_window_end);
          if (localDateTime) endField.value = localDateTime;
        }
      }
    };

    const stopRecording = () => {
      if (mediaRecorder && isRecording) {
        mediaRecorder.stop();
        isRecording = false;
        voiceBtn.classList.remove("recording");
        voiceBtn.disabled = false;
        voiceBtn.querySelector(".voice-btn-text").textContent = "Use Voice Input";
        updateVoiceStatus("Processing audio...", "processing");
      }
    };

    const startRecording = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioChunks = [];
        mediaRecorder = new MediaRecorder(stream, {
          mimeType: "audio/webm;codecs=opus"
        });

        mediaRecorder.ondataavailable = (event) => {
          if (event.data.size > 0) {
            audioChunks.push(event.data);
          }
        };

        mediaRecorder.onstop = async () => {
          stream.getTracks().forEach((track) => track.stop());

          if (audioChunks.length === 0) {
            updateVoiceStatus("No audio recorded. Please try again.", "error");
            return;
          }

          try {
            updateVoiceStatus("Transcribing audio...", "processing");

            // Create audio blob
            const audioBlob = new Blob(audioChunks, { type: "audio/webm" });
            const formData = new FormData();
            formData.append("audio", audioBlob, "recording.webm");

            // Transcribe audio
            const transcribeResponse = await fetch("/api/orders/transcribe-audio", {
              method: "POST",
              body: formData
            });

            if (!transcribeResponse.ok) {
              const errorData = await transcribeResponse.json().catch(() => ({}));
              throw new Error(errorData.detail || "Failed to transcribe audio");
            }

            const transcribeData = await transcribeResponse.json();
            const transcription = transcribeData.transcription;

            if (!transcription || !transcription.trim()) {
              updateVoiceStatus("No speech detected. Please try again.", "error");
              return;
            }

            updateVoiceStatus("Parsing information...", "processing");

            // Parse the transcribed text
            const parseResponse = await fetch("/api/orders/parse-text-only", {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                Accept: "application/json"
              },
              body: JSON.stringify({
                text: transcription,
                source: "voice_input"
              })
            });

            if (!parseResponse.ok) {
              const errorData = await parseResponse.json().catch(() => ({}));
              throw new Error(errorData.detail || "Failed to parse text");
            }

            const parsedData = await parseResponse.json();

            // Populate form fields
            populateFormFields(parsedData);

            updateVoiceStatus("Form populated successfully! Review and submit.", "success");
            clearMessage();

            // Clear status after 5 seconds
            setTimeout(() => {
              updateVoiceStatus("");
            }, 5000);
          } catch (error) {
            console.error("Voice input error:", error);
            updateVoiceStatus(error.message || "Error processing voice input. Please try again.", "error");
            setTimeout(() => {
              updateVoiceStatus("");
            }, 5000);
          }
        };

        mediaRecorder.start();
        isRecording = true;
        voiceBtn.classList.add("recording");
        voiceBtn.querySelector(".voice-btn-text").textContent = "Stop Recording";
        updateVoiceStatus("Recording... Click again to stop.", "recording");
      } catch (error) {
        console.error("Error accessing microphone:", error);
        updateVoiceStatus("Microphone access denied. Please allow microphone access and try again.", "error");
        setTimeout(() => {
          updateVoiceStatus("");
        }, 5000);
      }
    };

    voiceBtn.addEventListener("click", () => {
      if (isRecording) {
        stopRecording();
      } else {
        startRecording();
      }
    });

      // Stop recording if user navigates away
    window.addEventListener("beforeunload", () => {
      if (isRecording && mediaRecorder) {
        mediaRecorder.stop();
      }
    });
  }

  // Mobile-friendly improvements
  // Improve input focus on mobile - scroll into view when keyboard appears
  const formInputs = document.querySelectorAll('input, textarea');
  formInputs.forEach(input => {
    input.addEventListener('focus', function() {
      // Delay to allow keyboard to appear first
      setTimeout(() => {
        const rect = this.getBoundingClientRect();
        const isVisible = rect.top >= 0 && rect.bottom <= window.innerHeight;
        if (!isVisible) {
          this.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      }, 300);
    });
  });

  // Add touch-friendly class to body for CSS targeting
  if ('ontouchstart' in window || navigator.maxTouchPoints > 0) {
    document.body.classList.add('touch-device');
  }
})();
