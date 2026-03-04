const API_BASE = window.API_BASE || `${window.location.protocol}//${window.location.hostname}:3000`;

const alertBox = document.getElementById("alertBox");
const authSection = document.getElementById("authSection");
const notesSection = document.getElementById("notesSection");
const userEmail = document.getElementById("userEmail");

const registerForm = document.getElementById("registerForm");
const loginForm = document.getElementById("loginForm");
const logoutBtn = document.getElementById("logoutBtn");

const noteForm = document.getElementById("noteForm");
const noteFormTitle = document.getElementById("noteFormTitle");
const noteTitleInput = document.getElementById("noteTitle");
const noteContentInput = document.getElementById("noteContent");
const cancelEditBtn = document.getElementById("cancelEditBtn");
const notesList = document.getElementById("notesList");

let editingNoteId = null;


function showAlert(message, type = "danger") {
   alertBox.className = `alert alert-${type}`;
   alertBox.textContent = message;
   alertBox.classList.remove("d-none");
}

function hideAlert() {
   alertBox.classList.add("d-none");
}

async function apiRequest(path, options = {}) {
   const response = await fetch(`${API_BASE}${path}`, {
      credentials: "include",
      headers: {
         "Content-Type": "application/json",
         ...(options.headers || {}),
      },
      ...options,
   });

   const contentType = response.headers.get("content-type") || "";
   const payload = contentType.includes("application/json")
      ? await response.json()
      : null;

   if (!response.ok) {
      const message = payload?.error || "Error inesperado";
      throw new Error(message);
   }

   return payload;
}

function setAuthUI(user) {
   if (user) {
      authSection.classList.add("d-none");
      notesSection.classList.remove("d-none");
      userEmail.textContent = user.email;
      return;
   }

   authSection.classList.remove("d-none");
   notesSection.classList.add("d-none");
   userEmail.textContent = "";
}

function resetNoteForm() {
   editingNoteId = null;
   noteFormTitle.textContent = "Crear nota";
   noteTitleInput.value = "";
   noteContentInput.value = "";
   cancelEditBtn.classList.add("d-none");
}

function renderNotes(notes) {
   notesList.innerHTML = "";

   if (!notes.length) {
      notesList.innerHTML = '<p class="text-muted">Todavía no tienes notas.</p>';
      return;
   }

   for (const note of notes) {
      const col = document.createElement("div");
      col.className = "col-12";

      col.innerHTML = `
         <article class="card p-3 note-card">
            <div class="d-flex justify-content-between gap-2">
               <h3 class="h6 m-0">${escapeHtml(note.title)}</h3>
               <small class="text-muted">${new Date(note.updated_at).toLocaleString()}</small>
            </div>
            <p class="my-2">${escapeHtml(note.content)}</p>
            <div class="d-flex gap-2">
               <button class="btn btn-outline-primary btn-sm" data-action="edit" data-id="${note.id}">Editar</button>
               <button class="btn btn-outline-danger btn-sm" data-action="delete" data-id="${note.id}">Eliminar</button>
            </div>
         </article>
      `;

      notesList.appendChild(col);
   }
}

function escapeHtml(value) {
   return value
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#039;");
}

async function loadNotes() {
   const notes = await apiRequest("/api/notes", { method: "GET" });
   renderNotes(notes);
}

async function initSession() {
   try {
      const payload = await apiRequest("/api/auth/me", { method: "GET" });
      setAuthUI(payload.user);
      await loadNotes();
   } catch (_error) {
      setAuthUI(null);
   }
}

registerForm.addEventListener("submit", async (event) => {
   event.preventDefault();
   hideAlert();

   try {
      const payload = await apiRequest("/api/auth/register", {
         method: "POST",
         body: JSON.stringify({
            email: document.getElementById("registerEmail").value.trim(),
            password: document.getElementById("registerPassword").value,
            confirm_password: document.getElementById("registerConfirmPassword").value,
         }),
      });

      setAuthUI(payload.user);
      showAlert("Registro correcto", "success");
      registerForm.reset();
      await loadNotes();
   } catch (error) {
      showAlert(error.message);
   }
});

loginForm.addEventListener("submit", async (event) => {
   event.preventDefault();
   hideAlert();

   try {
      const payload = await apiRequest("/api/auth/login", {
         method: "POST",
         body: JSON.stringify({
            email: document.getElementById("loginEmail").value.trim(),
            password: document.getElementById("loginPassword").value,
         }),
      });

      setAuthUI(payload.user);
      showAlert("Sesión iniciada", "success");
      loginForm.reset();
      await loadNotes();
   } catch (error) {
      showAlert(error.message);
   }
});

logoutBtn.addEventListener("click", async () => {
   hideAlert();

   try {
      await apiRequest("/api/auth/logout", { method: "POST" });
      setAuthUI(null);
      resetNoteForm();
      notesList.innerHTML = "";
      showAlert("Sesión cerrada", "success");
   } catch (error) {
      showAlert(error.message);
   }
});

noteForm.addEventListener("submit", async (event) => {
   event.preventDefault();
   hideAlert();

   const payload = {
      title: noteTitleInput.value.trim(),
      content: noteContentInput.value.trim(),
   };

   try {
      if (editingNoteId === null) {
         await apiRequest("/api/notes", {
            method: "POST",
            body: JSON.stringify(payload),
         });
         showAlert("Nota creada", "success");
      } else {
         await apiRequest(`/api/notes/${editingNoteId}`, {
            method: "PUT",
            body: JSON.stringify(payload),
         });
         showAlert("Nota actualizada", "success");
      }

      resetNoteForm();
      await loadNotes();
   } catch (error) {
      showAlert(error.message);
   }
});

cancelEditBtn.addEventListener("click", () => {
   resetNoteForm();
});

notesList.addEventListener("click", async (event) => {
   const target = event.target;
   if (!(target instanceof HTMLButtonElement)) {
      return;
   }

   const noteId = Number(target.dataset.id);
   const action = target.dataset.action;

   if (!Number.isInteger(noteId)) {
      return;
   }

   hideAlert();

   try {
      if (action === "edit") {
         const note = await apiRequest(`/api/notes/${noteId}`, { method: "GET" });
         editingNoteId = note.id;
         noteFormTitle.textContent = "Editar nota";
         noteTitleInput.value = note.title;
         noteContentInput.value = note.content;
         cancelEditBtn.classList.remove("d-none");
         return;
      }

      if (action === "delete") {
         await apiRequest(`/api/notes/${noteId}`, { method: "DELETE" });
         showAlert("Nota eliminada", "success");
         if (editingNoteId === noteId) {
            resetNoteForm();
         }
         await loadNotes();
      }
   } catch (error) {
      showAlert(error.message);
   }
});

initSession();