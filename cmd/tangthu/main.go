package main

import (
	"encoding/json"
	"fmt"
	"html/template"
	"log"
	"net/http"
	"sort"
	"strings"
	"sync"
	"time"
)

type BranchStatus string
const (
	StatusOnline BranchStatus = "online"
	StatusHidden BranchStatus = "hidden"
	StatusUnavailable BranchStatus = "unavailable"
)

type FileEntry struct {
	ID string `json:"id"`
	ParentID string `json:"parent_id"`
	Name string `json:"name"`
	MIME string `json:"mime"`
	Size int64 `json:"size"`
	Modified string `json:"modified"`
	Checksum string `json:"checksum,omitempty"`
	IsFolder bool `json:"is_folder"`
}

type Branch struct {
	ID string `json:"id"`
	DisplayName string `json:"display_name"`
	RootFolderID string `json:"root_folder_id"`
	Status BranchStatus `json:"status"`
	LastScan string `json:"last_scan,omitempty"`
	Error string `json:"error,omitempty"`
	Files []FileEntry `json:"files"`
}

type Catalog struct {
	mu sync.RWMutex
	Branches []Branch
}

func vnPriority(s string) bool { return strings.HasPrefix(s, "VN") }

func branchLess(a, b Branch) bool {
	av, bv := vnPriority(a.DisplayName), vnPriority(b.DisplayName)
	if av != bv { return av }
	return strings.ToLower(a.DisplayName) < strings.ToLower(b.DisplayName)
}

func (c *Catalog) PublicBranches() []Branch {
	c.mu.RLock(); defer c.mu.RUnlock()
	var out []Branch
	for _, b := range c.Branches {
		if b.Status == StatusOnline { out = append(out, b) }
	}
	sort.SliceStable(out, func(i,j int) bool { return branchLess(out[i],out[j]) })
	return out
}

func (c *Catalog) AdminBranches() []Branch {
	c.mu.RLock(); defer c.mu.RUnlock()
	out := append([]Branch(nil), c.Branches...)
	sort.SliceStable(out, func(i,j int) bool { return branchLess(out[i],out[j]) })
	return out
}

func (c *Catalog) toggle(id string) {
	c.mu.Lock(); defer c.mu.Unlock()
	for i := range c.Branches {
		if c.Branches[i].ID == id {
			if c.Branches[i].Status == StatusHidden { c.Branches[i].Status = StatusOnline } else if c.Branches[i].Status == StatusOnline { c.Branches[i].Status = StatusHidden }
		}
	}
}

func (c *Catalog) unavailable(id, reason string) {
	c.mu.Lock(); defer c.mu.Unlock()
	for i := range c.Branches {
		if c.Branches[i].ID == id {
			c.Branches[i].Status = StatusUnavailable
			c.Branches[i].Error = reason
		}
	}
}

func sampleCatalog() *Catalog {
	return &Catalog{Branches: []Branch{
		{ID:"1", DisplayName:"VN Y Khoa", RootFolderID:"demo-vn", Status:StatusOnline, LastScan:time.Now().Format(time.RFC3339), Files: []FileEntry{
			{ID:"f1",ParentID:"root",Name:"Anatomy",IsFolder:true},
			{ID:"f2",ParentID:"root",Name:"Surgery",IsFolder:true},
			{ID:"f3",ParentID:"f2",Name:"Cleft.pdf",MIME:"application/pdf",Size:8400000,Modified:"2026-09-12",Checksum:"8f31..."},
		}},
		{ID:"2", DisplayName:"VN Văn học", RootFolderID:"demo-literature", Status:StatusOnline, LastScan:time.Now().Format(time.RFC3339)},
		{ID:"3", DisplayName:"English Library", RootFolderID:"demo-en", Status:StatusOnline, LastScan:time.Now().Format(time.RFC3339)},
		{ID:"4", DisplayName:"Old Books", RootFolderID:"missing", Status:StatusUnavailable, Error:"Root folder not found or inaccessible", LastScan:time.Now().Format(time.RFC3339)},
		{ID:"5", DisplayName:"Random Books", RootFolderID:"hidden", Status:StatusHidden, LastScan:time.Now().Format(time.RFC3339)},
	}}
}

var page = template.Must(template.New("page").Parse(`<!doctype html>
<html><head><meta charset="utf-8"><title>TÀNG THƯ OPDS</title>
<style>
body{font-family:Tahoma,Arial,sans-serif;background:#c0c0c0;margin:24px;color:#111}
.window{background:#ddd;border:2px solid #fff;border-right-color:#555;border-bottom-color:#555;max-width:980px;margin:auto}
.title{background:#000080;color:white;padding:5px 8px;font-weight:bold}.body{padding:16px}
table{width:100%;border-collapse:collapse;background:#fff}th,td{border:1px solid #888;padding:6px;text-align:left}th{background:#ddd}
button{font:inherit}a{color:#000080}.notice{background:#ffffcc;border:1px solid #888;padding:8px;margin:10px 0}
.status-online{color:green}.status-hidden{color:#666}.status-unavailable{color:#a00}
</style></head><body><div class="window"><div class="title">TÀNG THƯ OPDS</div><div class="body">
{{if .Admin}}
<h2>Branches — Admin</h2>
{{else}}<h2>Thư viện</h2><div class="notice">Các thư viện có tên bắt đầu chính xác bằng <b>VN</b> được ưu tiên hiển thị trước.</div>{{end}}
<table><tr><th>Tên</th><th>Trạng thái</th><th>Last scan</th>{{if .Admin}}<th>Action</th>{{end}}</tr>
{{range .Branches}}<tr><td>{{.DisplayName}}</td><td class="status-{{.Status}}">{{.Status}}{{if .Error}} — {{.Error}}{{end}}</td><td>{{.LastScan}}</td>{{if $.Admin}}<td><form method="post" action="/admin/toggle"><input type="hidden" name="id" value="{{.ID}}"><button>{{if eq .Status "hidden"}}Restore{{else}}Hide{{end}}</button></form></td>{{end}}</tr>{{end}}</table>
<p><a href="/opds">OPDS root</a> · <a href="/admin">Admin</a></p>
</div></div></body></html>`))

func main() {
	cat := sampleCatalog()
	http.HandleFunc("/", func(w http.ResponseWriter,r *http.Request){ http.Redirect(w,r,"/library",http.StatusFound) })
	http.HandleFunc("/library", func(w http.ResponseWriter,r *http.Request){ _=page.Execute(w,map[string]any{"Branches":cat.PublicBranches(),"Admin":false}) })
	http.HandleFunc("/admin", func(w http.ResponseWriter,r *http.Request){ _=page.Execute(w,map[string]any{"Branches":cat.AdminBranches(),"Admin":true}) })
	http.HandleFunc("/admin/toggle", func(w http.ResponseWriter,r *http.Request){ if r.Method=="POST" { _=r.ParseForm(); cat.toggle(r.Form.Get("id")) }; http.Redirect(w,r,"/admin",http.StatusFound) })
	http.HandleFunc("/opds", func(w http.ResponseWriter,r *http.Request){
		type Entry struct{Name,Href,Kind string}
		var e []Entry
		for _,b:=range cat.PublicBranches(){ e=append(e,Entry{b.DisplayName,"/opds/branch/"+b.ID,"acquisition"}) }
		w.Header().Set("Content-Type","application/atom+xml;profile=opds-catalog")
		fmt.Fprint(w,`<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom" xmlns:opds="http://opds-spec.org/2010/catalog"><title>TÀNG THƯ OPDS</title>`)
		for _,x:=range e { fmt.Fprintf(w,`<entry><title>%s</title><link rel="subsection" href="%s" type="application/atom+xml;profile=opds-catalog"/></entry>`,template.HTMLEscapeString(x.Name),x.Href) }
		fmt.Fprint(w,"</feed>")
	})
	http.HandleFunc("/opds/branch/", func(w http.ResponseWriter,r *http.Request){ w.Header().Set("Content-Type","application/atom+xml;profile=opds-catalog"); fmt.Fprint(w,`<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><title>Branch</title><entry><title>Prototype folder tree</title></entry></feed>`) })
	log.Println("TÀNG THƯ OPDS prototype listening on http://127.0.0.1:8080")
	log.Fatal(http.ListenAndServe(":8080",nil))
}

var _ = json.Valid
