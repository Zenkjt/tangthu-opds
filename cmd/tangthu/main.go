package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"html/template"
	"io"
	"log"
	"net/http"
	"net/url"
	"os"
	"path"
	"sort"
	"strconv"
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
	if vnPriority(a.DisplayName) != vnPriority(b.DisplayName) {
		return vnPriority(a.DisplayName)
	}
	return strings.ToLower(a.DisplayName) < strings.ToLower(b.DisplayName)
}
func (c *Catalog) PublicBranches() []Branch {
	c.mu.RLock()
	defer c.mu.RUnlock()
	out := []Branch{}
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
func (c *Catalog) save(file string) error {
	c.mu.RLock()
	data, err := json.MarshalIndent(persistedCatalog{c.Branches}, "", "  ")
	c.mu.RUnlock()
	if err != nil {
		return err
	}
	if d := path.Dir(file); d != "." {
		if err := os.MkdirAll(d, 0700); err != nil {
			return err
		}
	}
	tmp := file + ".tmp"
	if err := os.WriteFile(tmp, data, 0600); err != nil {
		return err
	}
	return os.Rename(tmp, file)
}
func loadCatalog(file string) (*Catalog, error) {
	data, err := os.ReadFile(file)
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
func (c *Catalog) rootAlreadyRegistered(id string) (Branch, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	for _, b := range c.Branches {
		if b.RootFolderID == id {
			return b, true
		}
	}
	return Branch{}, false
}
func (c *Catalog) add(b Branch) { c.mu.Lock(); defer c.mu.Unlock(); c.Branches = append(c.Branches, b) }
func (c *Catalog) toggle(id string) bool {
	c.mu.Lock()
	defer c.mu.Unlock()
	for i := range c.Branches {
		if c.Branches[i].ID != id {
			continue
		}
		if c.Branches[i].Status == StatusOnline {
			c.Branches[i].Status = StatusHidden
		} else if c.Branches[i].Status == StatusHidden {
			c.Branches[i].Status = StatusOnline
			c.Branches[i].Error = ""
		} else {
			return false
		}
		return true
	}
	return false
}
func (c *Catalog) rename(id, name string) bool {
	name = strings.TrimSpace(name)
	if name == "" {
		return false
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	for i := range c.Branches {
		if c.Branches[i].ID == id {
			c.Branches[i].DisplayName = name
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
	p := strings.Split(strings.TrimRight(raw, "/"), "/")
	for i, v := range p {
		if v == "folders" && i+1 < len(p) {
			return strings.Split(p[i+1], "?")[0]
		}
	}
	return ""
}
func convertFiles(in []drive.File) []FileEntry {
	out := make([]FileEntry, 0, len(in))
	for _, f := range in {
		out = append(out, FileEntry{f.ID, f.ParentID, f.Name, f.MIMEType, f.Size, f.ModifiedTime, f.MD5Checksum, drive.IsFolder(f)})
	}
	return out
}

type app struct {
	cat                            *Catalog
	drive                          *drive.Client
	dataFile, adminUser, adminPass string
}

func (a *app) scan(ctx context.Context, id string) error {
	b, ok := a.cat.find(id)
	if !ok {
		return errors.New("branch not found")
	}
	fs, err := a.drive.Scan(ctx, b.RootFolderID)
	if err != nil {
		a.cat.setScan(id, nil, err)
		_ = a.cat.save(a.dataFile)
		return err
	}
	a.cat.setScan(id, convertFiles(fs), nil)
	return a.cat.save(a.dataFile)
}
func (a *app) refreshAll(ctx context.Context) {
	for _, b := range a.cat.AdminBranches() {
		if b.Status != StatusHidden {
			if err := a.scan(ctx, b.ID); err != nil {
				log.Printf("scan %s: %v", b.DisplayName, err)
			}
		}
	}
}
func (a *app) auth(w http.ResponseWriter, r *http.Request) bool {
	if a.adminPass == "" {
		http.Error(w, "admin disabled", 503)
		return false
	}
	u, p, ok := r.BasicAuth()
	if !ok || u != a.adminUser || p != a.adminPass {
		w.Header().Set("WWW-Authenticate", `Basic realm="TANG THU Admin"`)
		http.Error(w, "authentication required", 401)
		return false
	}
	return true
}

func children(b Branch, parent string) []FileEntry {
	out := []FileEntry{}
	for _, f := range b.Files {
		if f.ParentID == parent {
			out = append(out, f)
		}
	}
	sort.SliceStable(out, func(i, j int) bool {
		if out[i].IsFolder != out[j].IsFolder {
			return out[i].IsFolder
		}
		return strings.ToLower(out[i].Name) < strings.ToLower(out[j].Name)
	})
	return out
}
func (a *app) folder(b Branch, id string) ([]FileEntry, bool) {
	if id == b.RootFolderID {
		return children(b, id), true
	}
	for _, f := range b.Files {
		if f.ID == id && f.IsFolder {
			return children(b, id), true
		}
	}
	return nil, false
}
func fileIn(b Branch, id string) (FileEntry, bool) {
	for _, f := range b.Files {
		if f.ID == id && !f.IsFolder {
			return f, true
		}
	}
	return FileEntry{}, false
}
func esc(s string) string { return template.HTMLEscapeString(s) }
func mime(s string) string {
	if s != "" {
		return s
	}
	return "application/octet-stream"
}

func (a *app) opdsRoot(w http.ResponseWriter, r *http.Request) {
	var x strings.Builder
	x.WriteString(`<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom" xmlns:opds="http://opds-spec.org/2010/catalog"><title>TÀNG THƯ</title><link rel="search" href="/opds/search.xml" type="application/opensearchdescription+xml"/>`)
	for _, b := range a.cat.PublicBranches() {
		x.WriteString(`<entry><title>` + esc(b.DisplayName) + `</title><link rel="subsection" href="/opds/branch/` + url.PathEscape(b.ID) + `" type="application/atom+xml;profile=opds-catalog"/></entry>`)
	}
	x.WriteString(`</feed>`)
	writeXML(w, x.String())
}
func (a *app) entry(b Branch, f FileEntry) string {
	if f.IsFolder {
		return `<entry><title>` + esc(f.Name) + `</title><link rel="subsection" href="/opds/folder/` + url.PathEscape(b.ID) + `/` + url.PathEscape(f.ID) + `" type="application/atom+xml;profile=opds-catalog"/></entry>`
	}
	return `<entry><title>` + esc(f.Name) + `</title><content type="text">` + esc(fmt.Sprintf("%d bytes · %s", f.Size, f.MIME)) + `</content><link rel="acquisition" href="/opds/acquire/` + url.PathEscape(b.ID) + `/` + url.PathEscape(f.ID) + `" type="` + esc(mime(f.MIME)) + `"/></entry>`
}
func (a *app) opdsBranch(w http.ResponseWriter, r *http.Request, id string) {
	b, ok := a.cat.find(id)
	if !ok || b.Status != StatusOnline {
		http.NotFound(w, r)
		return
	}
	var x strings.Builder
	x.WriteString(`<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom" xmlns:opds="http://opds-spec.org/2010/catalog"><title>` + esc(b.DisplayName) + `</title><link rel="start" href="/opds" type="application/atom+xml;profile=opds-catalog"/><link rel="search" href="/opds/search.xml" type="application/opensearchdescription+xml"/>`)
	for _, f := range children(b, b.RootFolderID) {
		x.WriteString(a.entry(b, f))
	}
	x.WriteString(`</feed>`)
	writeXML(w, x.String())
}
func (a *app) opdsFolder(w http.ResponseWriter, r *http.Request, id, fid string) {
	b, ok := a.cat.find(id)
	if !ok || b.Status != StatusOnline {
		http.NotFound(w, r)
		return
	}
	rows, ok := a.folder(b, fid)
	if !ok {
		http.NotFound(w, r)
		return
	}
	var x strings.Builder
	x.WriteString(`<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom" xmlns:opds="http://opds-spec.org/2010/catalog"><title>` + esc(b.DisplayName) + `</title><link rel="start" href="/opds" type="application/atom+xml;profile=opds-catalog"/><link rel="search" href="/opds/search.xml" type="application/opensearchdescription+xml"/>`)
	for _, f := range rows {
		x.WriteString(a.entry(b, f))
	}
	x.WriteString(`</feed>`)
	writeXML(w, x.String())
}
func (a *app) search(w http.ResponseWriter, r *http.Request) {
	q := strings.ToLower(strings.TrimSpace(r.URL.Query().Get("q")))
	var x strings.Builder
	x.WriteString(`<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom" xmlns:opds="http://opds-spec.org/2010/catalog"><title>Search: ` + esc(q) + `</title>`)
	if q != "" {
		for _, b := range a.cat.PublicBranches() {
			for _, f := range b.Files {
				if !f.IsFolder && (strings.Contains(strings.ToLower(f.Name), q) || strings.Contains(strings.ToLower(f.Checksum), q)) {
					x.WriteString(a.entry(b, f))
				}
			}
		}
	}
	x.WriteString(`</feed>`)
	writeXML(w, x.String())
}
func (a *app) openSearch(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/opensearchdescription+xml;charset=utf-8")
	io.WriteString(w, `<?xml version="1.0" encoding="UTF-8"?><OpenSearchDescription xmlns="http://a9.com/-/spec/opensearch/1.1/"><ShortName>TÀNG THƯ</ShortName><Description>Search TÀNG THƯ</Description><Url type="application/atom+xml" template="/opds/search?q={searchTerms}"/></OpenSearchDescription>`)
}
func writeXML(w http.ResponseWriter, s string) {
	w.Header().Set("Content-Type", "application/atom+xml;profile=opds-catalog;charset=utf-8")
	io.WriteString(w, s)
}

func (a *app) acquire(w http.ResponseWriter, r *http.Request, id, fid string) {
	b, ok := a.cat.find(id)
	if !ok || b.Status != StatusOnline {
		http.NotFound(w, r)
		return
	}
	f, ok := fileIn(b, fid)
	if !ok {
		http.NotFound(w, r)
		return
	}
	if r.Method == http.MethodHead {
		w.Header().Set("Content-Type", mime(f.MIME))
		if f.Size > 0 {
			w.Header().Set("Content-Length", strconv.FormatInt(f.Size, 10))
		}
		w.Header().Set("Accept-Ranges", "bytes")
		return
	}
	resp, err := a.drive.Open(r.Context(), fid, r.Header.Get("Range"))
	if err != nil {
		http.Error(w, "file acquisition failed", 502)
		return
	}
	defer resp.Body.Close()
	for _, h := range []string{"Content-Type", "Content-Length", "Content-Range", "Accept-Ranges", "ETag", "Last-Modified"} {
		if v := resp.Header.Get(h); v != "" {
			w.Header().Set(h, v)
		}
	}
	if w.Header().Get("Content-Type") == "" {
		w.Header().Set("Content-Type", mime(f.MIME))
	}
	w.WriteHeader(resp.StatusCode)
	_, _ = io.Copy(w, resp.Body)
}

var tpl = template.Must(template.New("page").Parse(`<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TÀNG THƯ</title><style>body{font:14px Tahoma,Arial;background:#c0c0c0;margin:24px}.w{max-width:1180px;margin:auto;background:#ddd;border:2px solid #fff;border-right-color:#555;border-bottom-color:#555}.t{background:#000080;color:#fff;padding:5px;font-weight:bold}.b{padding:16px}table{width:100%;border-collapse:collapse;background:#fff}th,td{border:1px solid #888;padding:6px;text-align:left}th{background:#ddd}a{color:#000080}.n{background:#ffffcc;border:1px solid #888;padding:8px;margin:10px 0}input,button{font:inherit;padding:4px}</style></head><body><div class=w><div class=t>TÀNG THƯ</div><div class=b>{{if .Admin}}<h2>Branches — Admin</h2><div class=n>Website public không có download.</div><form method=post action=/admin/validate><input name=url size=70 placeholder="Google Drive shared folder URL or ID" required> <button>Validate Folder</button></form>{{else}}<h2>Thư viện</h2><div class=n>Branch bắt đầu chính xác bằng <b>VN</b> được ưu tiên.</div><form method=get action=/search><input name=q value="{{.Query}}" size=55 placeholder="Tên file hoặc checksum"> <button>Search</button></form>{{end}}<table><tr><th>Tên</th><th>Status</th><th>Last scan</th>{{if .Admin}}<th>Action</th>{{end}}</tr>{{range .Branches}}<tr><td>{{if $.Admin}}{{.DisplayName}}<br><small>Drive: {{.DriveFolderName}}</small>{{else}}<a href="/library/branch/{{.ID}}">{{.DisplayName}}</a>{{end}}</td><td>{{.Status}}{{if .Error}} — {{.Error}}{{end}}</td><td>{{.LastScan}}</td>{{if $.Admin}}<td><form method=post action=/admin/toggle style="display:inline"><input type=hidden name=id value="{{.ID}}"><button>{{if eq .Status "hidden"}}Restore{{else}}Hide{{end}}</button></form> <form method=post action=/admin/rename style="display:inline"><input type=hidden name=id value="{{.ID}}"><input name=name value="{{.DisplayName}}" size=18><button>Rename</button></form> <form method=post action=/admin/refresh style="display:inline"><input type=hidden name=id value="{{.ID}}"><button>Refresh</button></form></td>{{end}}</tr>{{end}}</table><p><a href=/opds>OPDS</a>{{if not .Admin}} · <a href=/admin>Admin</a>{{end}}</p></div></div></body></html>`))
var branchTpl = template.Must(template.New("branch").Parse(`<!doctype html><html><head><meta charset=utf-8><title>{{.Branch.DisplayName}}</title><style>body{font:14px Tahoma;background:#c0c0c0;margin:24px}.w{max-width:1180px;margin:auto;background:#ddd;border:2px solid #fff;border-right-color:#555;border-bottom-color:#555}.t{background:#000080;color:#fff;padding:5px;font-weight:bold}.b{padding:16px}table{width:100%;border-collapse:collapse;background:#fff}th,td{border:1px solid #888;padding:6px;text-align:left}th{background:#ddd}a{color:#000080}</style></head><body><div class=w><div class=t>TÀNG THƯ — {{.Branch.DisplayName}}</div><div class=b><p><a href=/library>← Thư viện</a> · <a href="/opds/branch/{{.Branch.ID}}">OPDS</a></p><table><tr><th>Name</th><th>Size</th><th>Modified</th><th>MIME</th><th>Checksum</th></tr>{{range .Rows}}<tr><td>{{if .IsFolder}}📁 <a href="/library/branch/{{$.Branch.ID}}/folder/{{.ID}}">{{.Name}}</a>{{else}}📄 {{.Name}}{{end}}</td><td>{{if .IsFolder}}—{{else}}{{.Size}}{{end}}</td><td>{{.Modified}}</td><td>{{.MIME}}</td><td>{{.Checksum}}</td></tr>{{end}}</table></div></div></body></html>`))
var validateTpl = template.Must(template.New("validate").Parse(`<!doctype html><html><body style="font:14px Tahoma;background:#c0c0c0;margin:24px"><div style="max-width:700px;margin:auto;background:#ddd;border:2px solid #fff;padding:16px"><h2>Register Branch</h2><p>Drive folder: <b>{{.Folder.Name}}</b></p><form method=post action=/admin/register><input type=hidden name=url value="{{.URL}}"><p>Branch name:<br><input name=name value="{{.Folder.Name}}" size=70 required></p><button>Register & Scan</button> <a href=/admin>Cancel</a></form></div></body></html>`))
var folderTpl = branchTpl

type view struct {
	Admin    bool
	Branches []Branch
	Branch   Branch
	Rows     []FileEntry
	Query    string
	URL      string
	Folder   drive.File
}

func (a *app) webLibrary(w http.ResponseWriter, r *http.Request) {
	_ = tpl.Execute(w, view{Branches: a.cat.PublicBranches()})
}
func (a *app) webBranch(w http.ResponseWriter, r *http.Request, id string) {
	b, ok := a.cat.find(id)
	if !ok || b.Status != StatusOnline {
		http.NotFound(w, r)
		return
	}
	_ = branchTpl.Execute(w, view{Branch: b, Rows: children(b, b.RootFolderID)})
}
func (a *app) webFolder(w http.ResponseWriter, r *http.Request, id, fid string) {
	b, ok := a.cat.find(id)
	if !ok || b.Status != StatusOnline {
		http.NotFound(w, r)
		return
	}
	rows, ok := a.folder(b, fid)
	if !ok {
		http.NotFound(w, r)
		return
	}
	_ = folderTpl.Execute(w, view{Branch: b, Rows: rows})
}
func (a *app) webSearch(w http.ResponseWriter, r *http.Request) {
	q := strings.TrimSpace(r.URL.Query().Get("q"))
	needle := strings.ToLower(q)
	rows := []FileEntry{}
	for _, b := range a.cat.PublicBranches() {
		for _, f := range b.Files {
			if !f.IsFolder && q != "" && (strings.Contains(strings.ToLower(f.Name), needle) || strings.Contains(strings.ToLower(f.Checksum), needle)) {
				rows = append(rows, f)
			}
		}
	}
	_ = branchTpl.Execute(w, view{Branch: Branch{DisplayName: "Search: " + q}, Rows: rows})
}

func (a *app) admin(w http.ResponseWriter, r *http.Request) {
	if !a.auth(w, r) {
		return
	}
	_ = tpl.Execute(w, view{Admin: true, Branches: a.cat.AdminBranches()})
}
func (a *app) validate(w http.ResponseWriter, r *http.Request) {
	if !a.auth(w, r) {
		return
	}
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", 405)
		return
	}
	raw := strings.TrimSpace(r.FormValue("url"))
	id := extractFolderID(raw)
	if id == "" {
		http.Error(w, "invalid Google Drive folder URL or ID", 400)
		return
	}
	f, err := a.drive.GetFolder(r.Context(), id)
	if err != nil {
		http.Error(w, "folder validation failed: "+err.Error(), 502)
		return
	}
	if old, ok := a.cat.rootAlreadyRegistered(f.ID); ok {
		http.Error(w, "folder already registered as "+old.DisplayName, 409)
		return
	}
	_ = validateTpl.Execute(w, view{URL: raw, Folder: f})
}
func (a *app) register(w http.ResponseWriter, r *http.Request) {
	if !a.auth(w, r) {
		return
	}
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", 405)
		return
	}
	raw, name := strings.TrimSpace(r.FormValue("url")), strings.TrimSpace(r.FormValue("name"))
	id := extractFolderID(raw)
	if id == "" || name == "" {
		http.Error(w, "folder and Branch name are required", 400)
		return
	}
	f, err := a.drive.GetFolder(r.Context(), id)
	if err != nil {
		http.Error(w, "folder validation failed: "+err.Error(), 502)
		return
	}
	if _, ok := a.cat.rootAlreadyRegistered(f.ID); ok {
		http.Error(w, "folder already registered", 409)
		return
	}
	bid, err := makeID()
	if err != nil {
		http.Error(w, "cannot create Branch ID", 500)
		return
	}
	a.cat.add(Branch{ID: bid, DisplayName: name, DriveFolderName: f.Name, RootFolderID: f.ID, Status: StatusOnline})
	if err := a.cat.save(a.dataFile); err != nil {
		http.Error(w, "catalog save failed", 500)
		return
	}
	if err := a.scan(r.Context(), bid); err != nil {
		http.Error(w, "initial scan failed: "+err.Error(), 502)
		return
	}
	http.Redirect(w, r, "/admin", 303)
}
func (a *app) toggle(w http.ResponseWriter, r *http.Request) {
	if !a.auth(w, r) {
		return
	}
	if !a.cat.toggle(r.FormValue("id")) {
		http.NotFound(w, r)
		return
	}
	_ = a.cat.save(a.dataFile)
	http.Redirect(w, r, "/admin", 303)
}
func (a *app) rename(w http.ResponseWriter, r *http.Request) {
	if !a.auth(w, r) {
		return
	}
	if !a.cat.rename(r.FormValue("id"), r.FormValue("name")) {
		http.Error(w, "invalid Branch/name", 400)
		return
	}
	_ = a.cat.save(a.dataFile)
	http.Redirect(w, r, "/admin", 303)
}
func (a *app) refresh(w http.ResponseWriter, r *http.Request) {
	if !a.auth(w, r) {
		return
	}
	if err := a.scan(r.Context(), r.FormValue("id")); err != nil {
		http.Error(w, "refresh failed: "+err.Error(), 502)
		return
	}
	http.Redirect(w, r, "/admin", 303)
}

func (a *app) route(w http.ResponseWriter, r *http.Request) {
	p := strings.Trim(r.URL.Path, "/")
	switch {
	case p == "" || p == "library":
		a.webLibrary(w, r)
	case p == "search":
		a.webSearch(w, r)
	case p == "opds" || p == "opds/":
		a.opdsRoot(w, r)
	case p == "opds/search.xml":
		a.openSearch(w, r)
	case strings.HasPrefix(p, "opds/search"):
		a.search(w, r)
	case strings.HasPrefix(p, "opds/branch/"):
		a.opdsBranch(w, r, strings.TrimPrefix(p, "opds/branch/"))
	case strings.HasPrefix(p, "opds/folder/"):
		v := strings.Split(strings.TrimPrefix(p, "opds/folder/"), "/")
		if len(v) != 2 {
			http.NotFound(w, r)
			return
		}
		a.opdsFolder(w, r, v[0], v[1])
	case strings.HasPrefix(p, "opds/acquire/"):
		v := strings.Split(strings.TrimPrefix(p, "opds/acquire/"), "/")
		if len(v) != 2 {
			http.NotFound(w, r)
			return
		}
		a.acquire(w, r, v[0], v[1])
	case p == "admin":
		a.admin(w, r)
	case p == "admin/validate":
		a.validate(w, r)
	case p == "admin/register":
		a.register(w, r)
	case p == "admin/toggle":
		a.toggle(w, r)
	case p == "admin/rename":
		a.rename(w, r)
	case p == "admin/refresh":
		a.refresh(w, r)
	case strings.HasPrefix(p, "library/branch/"):
		v := strings.Split(strings.TrimPrefix(p, "library/branch/"), "/")
		if len(v) == 1 {
			a.webBranch(w, r, v[0])
			return
		}
		if len(v) == 3 && v[1] == "folder" {
			a.webFolder(w, r, v[0], v[2])
			return
		}
		http.NotFound(w, r)
	default:
		http.NotFound(w, r)
	}
}

func main() {
	key := strings.TrimSpace(os.Getenv("TANGTHU_GOOGLE_API_KEY"))
	if key == "" {
		log.Fatal("TANGTHU_GOOGLE_API_KEY is required")
	}
	file := os.Getenv("TANGTHU_DATA_FILE")
	if file == "" {
		file = "data/catalog.json"
	}
	cat, err := loadCatalog(file)
	if err != nil {
		log.Fatal(err)
	}
	d, err := drive.NewClient(key)
	if err != nil {
		log.Fatal(err)
	}
	u := os.Getenv("TANGTHU_ADMIN_USER")
	if u == "" {
		u = "admin"
	}
	a := &app{cat: cat, drive: d, dataFile: file, adminUser: u, adminPass: os.Getenv("TANGTHU_ADMIN_PASSWORD")}
	m := http.NewServeMux()
	m.HandleFunc("/", a.route)
	addr := os.Getenv("TANGTHU_LISTEN")
	if addr == "" {
		addr = "127.0.0.1:8080"
	}
	go func() {
		t := time.NewTicker(time.Hour)
		defer t.Stop()
		for range t.C {
			ctx, c := context.WithTimeout(context.Background(), 30*time.Minute)
			a.refreshAll(ctx)
			c()
		}
	}()
	log.Printf("TÀNG THƯ OPDS v1.0 listening on http://%s", addr)
	log.Fatal(http.ListenAndServe(addr, m))
}
