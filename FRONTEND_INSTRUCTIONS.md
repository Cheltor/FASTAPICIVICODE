# Frontend Instructions for Document Templates

The backend now supports uploading, listing, and using custom Word (.docx) templates for Violation Notices, Compliance Letters, and Licenses.

## 1. Uploading a New Template

**Endpoint:** `POST /templates/`

**Usage:**
Provide a form with:
*   `file`: The `.docx` file selected by the user.
*   `name`: A user-friendly name for the template.
*   `category`: One of `violation`, `compliance`, or `license`.

**Validation:**
The server validates that the file is a valid `.docx` and that it can be rendered with sample data. If validation fails, a `400 Bad Request` with an error message is returned.

**Example Fetch:**
```javascript
const formData = new FormData();
formData.append('file', fileInput.files[0]);
formData.append('name', "My Custom Violation Notice");
formData.append('category', "violation");

await fetch('/templates/', {
    method: 'POST',
    body: formData
});
```

## 2. Listing Templates

**Endpoint:** `GET /templates/?category={category}`

**Usage:**
When a user is about to generate a document (e.g., on the Violation Details page), fetch the list of available templates for that category.

**Response:**
Returns a list of template objects:
```json
[
    {
        "id": 1,
        "name": "My Custom Violation Notice",
        "category": "violation",
        "filename": "custom_v1.docx",
        "created_at": "..."
    }
]
```

**UI Suggestion:**
Add a dropdown menu labeled "Template" next to the "Print" or "Generate" button.
*   Default option: "System Default" (value `null` or empty).
*   Other options: The names of the templates returned by this endpoint, with their `id` as the value.

## 3. Generating Documents

**Endpoints Updated:**
*   `GET /violation/{id}/notice`
*   `GET /violation/{id}/compliance-letter`
*   `GET /license/{id}/download`

**Usage:**
Append the `template_id` query parameter if a custom template is selected.

**Example:**
*   Default: `GET /violation/123/notice`
*   Custom: `GET /violation/123/notice?template_id=5`

## 4. Deleting Templates

**Endpoint:** `DELETE /templates/{id}`

**Usage:**
Allow users to manage the library of templates. You might want a "Settings > Templates" page where they can see all uploaded templates and delete old ones.

## 5. Downloading Templates

**Endpoint:** `GET /templates/{id}/download`

**Usage:**
Allow users to download the original uploaded file to edit it and re-upload.
