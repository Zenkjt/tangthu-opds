package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"html"
	"html/template"
	"log"
	"net/http"
	"os"
	"path"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/Zenkjt/tangthu-opds/internal/drive"
)

type BranchStatus string

const (
	StatusOnline      BranchStatus = "online"
	StatusHidden      BranchStatus = "hidden"
	StatusUnavailable BranchStatus = "unavailable"
)

type FileEntry struct {
	ID       string `json:"id"`
	ParentID string `json:"parent_id"`
	Name     string `json:"name"`
	MIME     string `json:"mime"`
	Size     int64  `json:"size"`
	Modified string `json:"modified"`
	Checksum string `json:"checksum,omitempty"`
	IsFolder bool   `json:"is_folder"`
}

type Branch struct {
	ID              string       `json:"id"`
	DisplayName     string       `json:"display_name"`
	DriveFolderName string       `json:"drive_folder_name,omitempty"`
	RootFolderID    string       `json:"root_folder_id"`
	Status          BranchStatus `json:"status"`
	LastScan        string       `json:"last_scan,omitempty"`
	Error           string       `json:"error,omitempty"`
	Files           []FileEntry  `json:"files"`
}

type Catalog struct {
	mu       sync.RWMutex
	Branches []Branch
}

type persistedCatalog struct {
	Branches []Branch `json:"branches"`
}

func vnPriority(s string) bool { return strings.HasPrefix(s, "VN") }

func branchLess(a, b Branch) bool {
	av, bv := vnPriority(a.DisplayName), vnPriority(b.DisplayName)
	if av != bv {
		return av
	}
	return strings.ToLower(a.DisplayName) < strings.ToLower(b.DisplayName)
}

func (c *Catalog) PublicBranches() []Branch {
	c.mu.RLock()
	defer c.mu.RUnlock()
	var out []Branch
	for _, b := range c.Branches {
		if b.Status == StatusOnline {
			out = append(out, b)
		}
	}
	sort.SliceStable(out, func(i, j int) bool { return branchLess(out[i], out[j]) })
	return out
}

func (c *Catalog) AdminBranches() []Branch {
	c.mu.RLock()
	defer c.mu.RUnlock()
	out := append([]Branch(nil), c.Branches...)
	sort.SliceStable(out, func(i, j int) bool { return branchLess(out[i], out[j]) })
	return out
}

func (c *Catalog) save(filename string) error {
	c.mu.RLock()
	data, err := json.MarshalIndent(persistedCatalog{Branches: c.Branches}, "", "  ")
	c.mu.RUnlock()
	if err != nil {
		return err
	}
	tmp := filename + ".tmp"
	if err := os.WriteFile(tmp, data, 0600); err != nil {
		return err
	}
	return os.Rename(tmp, filename)
}

func loadCatalog(filename string) (*Catalog, error) {
	data, err := os.ReadFile(filename)
	if errors.Is(err, os.ErrNotExist) {
		return &Catalog{}, nil
	}
	if err != nil {
		return nil, err
	}
	var p persistedCatalog
	if err := json.Unmarshal(data, &p); err != nil {
		return nil, err
	}
	return &Catalog{Branches: p.Branches}, nil
}

func (c *Catalog) find(id string) (Branch, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	for _, b := range c.Branches {
		if b.ID == id {
			return b, true
		}
	}
	return Branch{}, false
}

func (c *Catalog) rootAlreadyRegistered(rootID string) (Branch, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	for _, b := range c.Branches {
		if b.RootFolderID == rootID {
			return b, true
		}
	}
	return Branch{}, false
}

func (c *Catalog) addOrUpdate(b Branch) {
	c.mu.Lock()
	defer c.mu.Unlock()
	for i := range c.Branches {
		if c.Branches[i].ID == b.ID {
			c.Branches[i] = b
			return
		}
	}
	c.Branches = append(c.Branches, b)
}

func (c *Catalog) toggle(id string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	for i := range c.Branches {
		if c.Branches[i].ID != id {
			continue
		}
		switch c.Branches[i].Status {
		case StatusHidden:
			c.Branches[i].Status = StatusOnline
			c.Branches[i].Error = ""
		case StatusOnline:
			c.Branches[i].Status = StatusHidden
		}
	}
}

func (c *Catalog) rename(id, name string) bool {
	c.mu.Lock()
	defer c.mu.Unlock()
	for i := range c.Branches {
		if c.Branches[i].ID == id {
			c.Branches[i].DisplayName = strings.TrimSpace(name)
			return true
		}
	}
	return false
}

func (c *Catalog) setScan(id string, files []FileEntry, err error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	for i := range c.Branches {
		if c.Branches[i].ID != id {
			continue
		}
		if err != nil {
			c.Branches[i].Status = StatusUnavailable
			c.Branches[i].Error = err.Error()
			return
		}
		c.Branches[i].Status = StatusOnline
		c.Branches[i].Error = ""
		c.Branches[i].Files = files
		c.Branches[i].LastScan = time.Now().Format(time.RFC3339)
	}
}

func makeID() (string, error) {
	var b [6]byte
	if _, err := rand.Read(b[:]); err != nil {
		return "", err
	}
	return hex.EncodeToString(b[:]), nil
}

func extractFolderID(raw string) string {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return ""
	}
	if !strings.Contains(raw, "://") && !strings.Contains(raw, "/") {
		return raw
	}
	parts := strings.Split(strings.TrimRight(raw, "/"), "/")
	for i, p := range parts {
		if p == "folders" && i+1 < len(parts) {
			return strings.Split(parts[i+1], "?")[0]
		}
	}
	return ""
}

func convertFiles(files []drive.File) []FileEntry {
	out := make([]FileEntry, 0, len(files))
	for _, f := range files {
		out = append(out, FileEntry{
			ID: f.ID, ParentID: f.ParentID, Name: f.Name, MIME: f.MIMEType,
			Size: f.Size, Modified: f.ModifiedTime, Checksum: f.MD5Checksum,
			IsFolder: drive.IsFolder(f),
		})
	}
	return out
}

type app struct {
	cat       *Catalog
	drive     *drive.Client
	dataFile  string
	adminUser string
	adminPass string
}

func (a *app) scanBranch(ctx context.Context, id string) error {
	b, ok := a.cat.find(id)
	if !ok {
		return errors.New("branch not found")
	}
	files, err := a.drive.Scan(ctx, b.RootFolderID)
	if err != nil {
		a.cat.setScan(id, nil, err)
		_ = a.cat.save(a.dataFile)
		return err
	}
	entries := convertFiles(files)
	a.cat.setScan(id, entries, nil)
	return a.cat.save(a.dataFile)
}

func (a *app) refreshAll(ctx context.Context) {
	for _, b := range a.cat.AdminBranches() {
		if b.Status == StatusHidden {
			continue
		}
		if err := a.scanBranch(ctx, b.ID); err != nil {
			log.Printf("scan %s (%s): %v", b.DisplayName, b.ID, err)
		}
	}
}

func (a *app) adminAuth(w http.ResponseWriter, r *http.Request) bool {
	if a.adminPass == "" {
		http.Error(w, "Admin access is disabled: set TANGTHU_ADMIN_PASSWORD", http.StatusServiceUnavailable)
		return false
	}
	user, pass, ok := r.BasicAuth()
	if !ok || user != a.adminUser || pass != a.adminPass {
		w.Header().Set("WWW-Authenticate", `Basic realm="TANG THU Admin"`)
		http.Error(w, "authentication required", http.StatusUnauthorized)
		return false
	}
	return true
}

var page = template.Must(template.New("page").Parse(`<!doctype html>
<html><head><meta charset="utf-8"><title>TÀNG THƯ OPDS</title>
<style>
body{font-family:Tahoma,Arial,sans-serif;background:#c0c0c0;margin:24px;color:#111}
.window{background:#ddd;border:2px solid #fff;border-right-color:#555;border-bottom-color:#555;max-width:1100px;margin:auto}
.title{background:#000080;color:white;padding:5px 8px;font-weight:bold}.body{padding:16px}
table{width:100%;border-collapse:collapse;background:#fff}th,td{border:1px solid #888;padding:6px;text-align:left}th{background:#ddd}
input{font:inherit;padding:4px}button{font:inherit}a{color:#000080}.notice{background:#ffffcc;border:1px solid #888;padding:8px;margin:10px 0}
.status-online{color:green}.status-hidden{color:#666}.status-unavailable{color:#a00}.muted{color:#555}
</style></head><body><div class="window"><div class="title">TÀNG THƯ OPDS</div><div class="body">
{{if .Admin}}
<h2>Branches — Admin</h2>
<div class="notice">Đây là vùng quản trị. Website công khai chỉ dùng để xem catalog; không có download.</div>
<h3>Register Branch</h3>
<form method="post" action="/admin/validate">
<p>Google Drive shared folder URL or ID:<br><input name="url" size="80" required></p>
<button>Validate Folder</button>
</form>
{{else}}
<h2>Thư viện</h2>
<div class="notice">Các thư viện có tên bắt đầu chính xác bằng <b>VN</b> được ưu tiên hiển thị trước.</div>
{{end}}
<table><tr><th>Tên</th><th>Trạng thái</th><th>Last scan</th>{{if .Admin}}<th>Action</th>{{end}}</tr>
{{range .Branches}}<tr>
<td>{{if not $.Admin}}<a href="/library/branch/{{.ID}}">{{.DisplayName}}</a>{{else}}{{.DisplayName}}<br><span class="muted">Drive: {{.DriveFolderName}}</span>{{end}}</td>
<td class="status-{{.Status}}">{{.Status}}{{if .Error}} — {{.Error}}{{end}}</td><td>{{.LastScan}}</td>
{{if $.Admin}}<td>
<form method="post" action="/admin/toggle" style="display:inline"><input type="hidden" name="id" value="{{.ID}}"><button>{{if eq .Status "hidden"}}Restore{{else}}Hide{{end}}</button></form>
<form method="post" action="/admin/rename" style="display:inline"><input type="hidden" name="id" value="{{.ID}}"><input name="name" value="{{.DisplayName}}" size="22"><button>Rename</button></form>
<form method="post" action="/admin/refresh" style="display:inline"><input type="hidden" name="id" value="{{.ID}}"><button>Refresh</button></form>
</td>{{end}}</tr>{{end}}</table>
{{if not .Admin}}<p><a href="/opds">OPDS root</a></p>{{end}}
</div></div></body></html>`))

var branchPage = template.Must(template.New("branch").Parse(`<!doctype html>
<html><head><meta charset="utf-8"><title>{{.Branch.DisplayName}} — TÀNG THƯ</title>
<style>
body{font-family:Tahoma,Arial,sans-serif;background:#c0c0c0;margin:24px;color:#111}
.window{background:#ddd;border:2px solid #fff;border-right-color:#555;border-bottom-color:#555;max-width:1100px;margin:auto}
.title{background:#000080;color:white;padding:5px 8px;font-weight:bold}.body{padding:16px}
table{width:100%;border-collapse:collapse;background:#fff}th,td{border:1px solid #888;padding:6px;text-align:left}th{background:#ddd}
a{color:#000080}.muted{color:#555}.notice{background:#ffffcc;border:1px solid #888;padding:8px;margin:10px 0}
</style></head><body><div class="window"><div class="title">TÀNG THƯ OPDS — {{.Branch.DisplayName}}</div><div class="body">
<p><a href="/library">← Thư viện</a> · <a href="/opds/branch/{{.Branch.ID}}">OPDS</a></p>
<div class="notice">Website chỉ hiển thị catalog. Không cung cấp file download.</div>
<table><tr><th>Name</th><th>Size</th><th>Modified</th><th>MIME</th><th>Checksum</th></tr>
{{range .Rows}}<tr>
<td>{{if .IsFolder}}📁 <a href="/library/branch/{{$.Branch.ID}}/folder/{{.ID}}">{{.Name}}</a>{{else}}📄 {{.Name}}{{end}}</td>
<td>{{if .IsFolder}}—{{else}}{{.Size}}{{end}}</td>
<td>{{.Modified}}</td><td>{{.MIME}}</td><td>{{.Checksum}}</td>
</tr>{{end}}</table>
</div></div></body></html>`))

var validatePage = template.Must(template.New("validate").Parse(`<!doctype html>
<html><head><meta charset="utf-8"><title>Register Branch — TÀNG THƯ</title>
<style>
body{font-family:Tahoma,Arial,sans-serif;background:#c0c0c0;margin:24px;color:#111}
.window{background:#ddd;border:2px solid #fff;border-right-color:#555;border-bottom-color:#555;max-width:900px;margin:auto}
.title{background:#000080;color:white;padding:5px 8px;font-weight:bold}.body{padding:16px}
input{font:inherit;padding:5px;width:100%;box-sizing:border-box}.readonly{background:#eee}.notice{background:#ffffcc;border:1px solid #888;padding:8px;margin:10px 0}
button{font:inherit;padding:5px 12px}
</style></head><body><div class="window"><div class="title">TÀNG THƯ OPDS — REGISTER BRANCH</div><div class="body">
<div class="notice">Folder đã được xác thực. Tên Google Drive chỉ là thông tin tham khảo; Branch name là tên riêng của TÀNG THƯ.</div>
<form method="post" action="/admin/register">
<input type="hidden" name="url" value="{{.URL}}">
<p>Google Drive folder name:</p><input class="readonly" value="{{.Folder.Name}}" readonly>
<p>Branch name:</p><input name="name" value="{{.Folder.Name}}" required autofocus>
<p><button>Save Branch</button> <a href="/admin">Cancel</a></p>
</form>
</div></div></body></html>`))

func (a *app) libraryBranch(w http.ResponseWriter, r *http.Request) {
	id := strings.TrimPrefix(r.URL.Path, "/library/branch/")
	b, ok := a.cat.find(id)
	if !ok || b.Status != StatusOnline {
		http.NotFound(w, r)
		return
	}
	var rows []FileEntry
	for _, f := range b.Files {
		if f.ParentID == b.RootFolderID {
			rows = append(rows, f)
		}
	}
	sort.Slice(rows, func(i, j int) bool {
		if rows[i].IsFolder != rows[j].IsFolder {
			return rows[i].IsFolder
		}
		return strings.ToLower(rows[i].Name) < strings.ToLower(rows[j].Name)
	})
	_ = branchPage.Execute(w, map[string]any{"Branch": b, "Rows": rows})
}

func (a *app) validate(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost || !a.adminAuth(w, r) {
		return
	}
	_ = r.ParseForm()
	rawURL := strings.TrimSpace(r.Form.Get("url"))
	rootID := extractFolderID(rawURL)
	if rootID == "" {
		http.Error(w, "Invalid Google Drive folder URL or ID", http.StatusBadRequest)
		return
	}
	if existing, ok := a.cat.rootAlreadyRegistered(rootID); ok {
		http.Error(w, fmt.Sprintf("This Google Drive folder is already registered as %q.", existing.DisplayName), http.StatusConflict)
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 20*time.Second)
	defer cancel()
	folder, err := a.drive.GetFolder(ctx, rootID)
	if err != nil {
		http.Error(w, "Google Drive folder validation failed: "+err.Error(), http.StatusBadRequest)
		return
	}
	_ = validatePage.Execute(w, map[string]any{"URL": rawURL, "Folder": folder})
}

func (a *app) libraryFolder(w http.ResponseWriter, r *http.Request) {
	rest := strings.TrimPrefix(r.URL.Path, "/library/branch/")
	parts := strings.SplitN(rest, "/folder/", 2)
	if len(parts) != 2 {
		http.NotFound(w, r)
		return
	}
	b, ok := a.cat.find(parts[0])
	if !ok || b.Status != StatusOnline {
		http.NotFound(w, r)
		return
	}
	folderID := parts[1]
	found := false
	for _, f := range b.Files {
		if f.ID == folderID && f.IsFolder {
			found = true
			break
		}
	}
	if !found {
		http.NotFound(w, r)
		return
	}
	var rows []FileEntry
	for _, f := range b.Files {
		if f.ParentID == folderID {
			rows = append(rows, f)
		}
	}
	sort.Slice(rows, func(i, j int) bool {
		if rows[i].IsFolder != rows[j].IsFolder {
			return rows[i].IsFolder
		}
		return strings.ToLower(rows[i].Name) < strings.ToLower(rows[j].Name)
	})
	_ = branchPage.Execute(w, map[string]any{"Branch": b, "Rows": rows})
}

func (a *app) register(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost || !a.adminAuth(w, r) {
		return
	}
	_ = r.ParseForm()
	rawURL := strings.TrimSpace(r.Form.Get("url"))
	name := strings.TrimSpace(r.Form.Get("name"))
	rootID := extractFolderID(rawURL)
	if rootID == "" || name == "" {
		http.Error(w, "Invalid folder URL/ID or Branch name", http.StatusBadRequest)
		return
	}
	if existing, ok := a.cat.rootAlreadyRegistered(rootID); ok {
		http.Error(w, fmt.Sprintf("This Google Drive folder is already registered as %q.", existing.DisplayName), http.StatusConflict)
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 2*time.Minute)
	defer cancel()
	folder, err := a.drive.GetFolder(ctx, rootID)
	if err != nil {
		http.Error(w, "Google Drive folder validation failed: "+err.Error(), http.StatusBadRequest)
		return
	}
	id, err := makeID()
	if err != nil {
		http.Error(w, "cannot generate Branch ID", http.StatusInternalServerError)
		return
	}
	b := Branch{ID: id, DisplayName: name, DriveFolderName: folder.Name, RootFolderID: folder.ID, Status: StatusOnline}
	a.cat.addOrUpdate(b)
	if err := a.cat.save(a.dataFile); err != nil {
		http.Error(w, "saved in memory but failed to persist: "+err.Error(), http.StatusInternalServerError)
		return
	}
	if err := a.scanBranch(ctx, id); err != nil {
		http.Error(w, "Branch saved but initial scan failed: "+err.Error(), http.StatusBadGateway)
		return
	}
	http.Redirect(w, r, "/admin", http.StatusSeeOther)
}

func (a *app) toggle(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost || !a.adminAuth(w, r) {
		return
	}
	_ = r.ParseForm()
	a.cat.toggle(r.Form.Get("id"))
	_ = a.cat.save(a.dataFile)
	http.Redirect(w, r, "/admin", http.StatusSeeOther)
}

func (a *app) rename(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost || !a.adminAuth(w, r) {
		return
	}
	_ = r.ParseForm()
	name := strings.TrimSpace(r.Form.Get("name"))
	if name != "" {
		a.cat.rename(r.Form.Get("id"), name)
		_ = a.cat.save(a.dataFile)
	}
	http.Redirect(w, r, "/admin", http.StatusSeeOther)
}

func (a *app) refresh(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost || !a.adminAuth(w, r) {
		return
	}
	_ = r.ParseForm()
	ctx, cancel := context.WithTimeout(r.Context(), 2*time.Minute)
	defer cancel()
	if err := a.scanBranch(ctx, r.Form.Get("id")); err != nil {
		http.Error(w, "Refresh failed: "+err.Error(), http.StatusBadGateway)
		return
	}
	http.Redirect(w, r, "/admin", http.StatusSeeOther)
}

func (a *app) opdsRoot(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", `application/atom+xml;profile=opds-catalog`)
	var sb strings.Builder
	sb.WriteString(`<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom" xmlns:opds="http://opds-spec.org/2010/catalog"><title>TÀNG THƯ</title>`)
	for _, b := range a.cat.PublicBranches() {
		fmt.Fprintf(&sb, `<entry><title>%s</title><link rel="subsection" href="/opds/branch/%s" type="application/atom+xml;profile=opds-catalog"/></entry>`, html.EscapeString(b.DisplayName), html.EscapeString(b.ID))
	}
	sb.WriteString("</feed>")
	fmt.Fprint(w, sb.String())
}

func (a *app) opdsBranch(w http.ResponseWriter, r *http.Request) {
	id := strings.TrimPrefix(r.URL.Path, "/opds/branch/")
	b, ok := a.cat.find(id)
	if !ok || b.Status != StatusOnline {
		http.NotFound(w, r)
		return
	}
	var rows []FileEntry
	for _, f := range b.Files {
		if f.ParentID == b.RootFolderID {
			rows = append(rows, f)
		}
	}
	a.writeOPDS(w, b.DisplayName, id, rows)
}

func (a *app) opdsFolder(w http.ResponseWriter, r *http.Request) {
	rest := strings.TrimPrefix(r.URL.Path, "/opds/folder/")
	parts := strings.SplitN(rest, "/", 2)
	if len(parts) != 2 {
		http.NotFound(w, r)
		return
	}
	b, ok := a.cat.find(parts[0])
	if !ok || b.Status != StatusOnline {
		http.NotFound(w, r)
		return
	}
	folderID := parts[1]
	var rows []FileEntry
	for _, f := range b.Files {
		if f.ParentID == folderID {
			rows = append(rows, f)
		}
	}
	a.writeOPDS(w, b.DisplayName, folderID, rows)
}

func (a *app) writeOPDS(w http.ResponseWriter, title, branchID string, rows []FileEntry) {
	w.Header().Set("Content-Type", `application/atom+xml;profile=opds-catalog`)
	var sb strings.Builder
	fmt.Fprintf(&sb, `<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom" xmlns:opds="http://opds-spec.org/2010/catalog"><title>%s</title>`, html.EscapeString(title))
	sort.Slice(rows, func(i, j int) bool {
		if rows[i].IsFolder != rows[j].IsFolder {
			return rows[i].IsFolder
		}
		return strings.ToLower(rows[i].Name) < strings.ToLower(rows[j].Name)
	})
	for _, f := range rows {
		if f.IsFolder {
			fmt.Fprintf(&sb, `<entry><title>%s</title><link rel="subsection" href="/opds/folder/%s/%s" type="application/atom+xml;profile=opds-catalog"/></entry>`, html.EscapeString(f.Name), html.EscapeString(branchID), html.EscapeString(f.ID))
		} else {
			// Acquisition is intentionally not enabled in v0.4 yet.
			fmt.Fprintf(&sb, `<entry><title>%s</title><link rel="acquisition" href="/opds/acquire/%s/%s" type="%s"/></entry>`, html.EscapeString(f.Name), html.EscapeString(branchID), html.EscapeString(f.ID), html.EscapeString(f.MIME))
		}
	}
	sb.WriteString("</feed>")
	fmt.Fprint(w, sb.String())
}

func (a *app) routes() {
	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) { http.Redirect(w, r, "/library", http.StatusFound) })
	http.HandleFunc("/library", func(w http.ResponseWriter, r *http.Request) {
		_ = page.Execute(w, map[string]any{"Branches": a.cat.PublicBranches(), "Admin": false})
	})
	http.HandleFunc("/library/branch/", func(w http.ResponseWriter, r *http.Request) {
		if strings.Contains(r.URL.Path, "/folder/") {
			a.libraryFolder(w, r)
			return
		}
		a.libraryBranch(w, r)
	})
	http.HandleFunc("/admin", func(w http.ResponseWriter, r *http.Request) {
		if !a.adminAuth(w, r) {
			return
		}
		_ = page.Execute(w, map[string]any{"Branches": a.cat.AdminBranches(), "Admin": true})
	})
	http.HandleFunc("/admin/validate", a.validate)
	http.HandleFunc("/admin/register", a.register)
	http.HandleFunc("/admin/toggle", a.toggle)
	http.HandleFunc("/admin/rename", a.rename)
	http.HandleFunc("/admin/refresh", a.refresh)
	http.HandleFunc("/opds", a.opdsRoot)
	http.HandleFunc("/opds/branch/", a.opdsBranch)
	http.HandleFunc("/opds/folder/", a.opdsFolder)
	http.HandleFunc("/opds/acquire/", func(w http.ResponseWriter, r *http.Request) {
		http.Error(w, "Acquisition gateway is reserved for the next implementation step.", http.StatusNotImplemented)
	})
}

func getenv(key, fallback string) string {
	if v := strings.TrimSpace(os.Getenv(key)); v != "" {
		return v
	}
	return fallback
}

func main() {
	apiKey := os.Getenv("TANGTHU_GOOGLE_API_KEY")
	if strings.TrimSpace(apiKey) == "" {
		log.Fatal("TANGTHU_GOOGLE_API_KEY is required")
	}
	drv, err := drive.NewClient(apiKey)
	if err != nil {
		log.Fatal(err)
	}
	dataFile := getenv("TANGTHU_DATA_FILE", "data/catalog.json")
	if err := os.MkdirAll(path.Dir(dataFile), 0700); err != nil {
		log.Fatal(err)
	}
	cat, err := loadCatalog(dataFile)
	if err != nil {
		log.Fatal(err)
	}
	a := &app{
		cat: cat, drive: drv, dataFile: dataFile,
		adminUser: getenv("TANGTHU_ADMIN_USER", "admin"),
		adminPass: os.Getenv("TANGTHU_ADMIN_PASSWORD"),
	}
	a.routes()

	go func() {
		ticker := time.NewTicker(time.Hour)
		defer ticker.Stop()
		for range ticker.C {
			ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
			a.refreshAll(ctx)
			cancel()
		}
	}()

	log.Println("TÀNG THƯ OPDS v0.4 listening on http://127.0.0.1:8080")
	log.Fatal(http.ListenAndServe(":8080", nil))
}
