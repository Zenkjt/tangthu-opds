package main

import (
	"context"
	"encoding/json"
	"fmt"
	"html"
	"net/url"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"github.com/Zenkjt/tangthu-opds/internal/drive"
)

type BranchConfig struct {
	ID           string `json:"id"`
	DisplayName  string `json:"display_name"`
	RootFolderID string `json:"root_folder_id"`
	Enabled      bool   `json:"enabled"`
}

type Config struct {
	Branches []BranchConfig `json:"branches"`
}

type FileEntry struct {
	ID       string
	ParentID string
	Name     string
	MIME     string
	Size     int64
	Modified string
	Checksum string
	IsFolder bool
}

type Branch struct {
	Config          BranchConfig
	DriveFolderName string
	Files           []FileEntry
}

func main() {
	apiKey := strings.TrimSpace(os.Getenv("TANGTHU_GOOGLE_API_KEY"))
	if apiKey == "" {
		fatal("TANGTHU_GOOGLE_API_KEY is required")
	}
	cfgPath := getenv("TANGTHU_BRANCH_CONFIG", "config/branches.json")
	outDir := getenv("TANGTHU_OUTPUT_DIR", "docs")
	baseURL := strings.TrimRight(getenv("TANGTHU_BASE_URL", "https://zenkjt.github.io/tangthu-opds"), "/")

	data, err := os.ReadFile(cfgPath)
	if err != nil {
		fatal(err.Error())
	}
	var cfg Config
	if err := json.Unmarshal(data, &cfg); err != nil {
		fatal(err.Error())
	}

	client, err := drive.NewClient(apiKey)
	if err != nil {
		fatal(err.Error())
	}
	ctx := context.Background()
	var branches []Branch
	for _, bc := range cfg.Branches {
		if !bc.Enabled {
			continue
		}
		folder, err := client.GetFolder(ctx, bc.RootFolderID)
		if err != nil {
			fatal(fmt.Sprintf("branch %s: %v", bc.ID, err))
		}
		files, err := client.Scan(ctx, bc.RootFolderID)
		if err != nil {
			fatal(fmt.Sprintf("scan %s: %v", bc.ID, err))
		}
		converted := make([]FileEntry, 0, len(files))
		for _, f := range files {
			converted = append(converted, FileEntry{f.ID, f.ParentID, f.Name, f.MIMEType, f.Size, f.ModifiedTime, f.MD5Checksum, drive.IsFolder(f)})
		}
		branches = append(branches, Branch{bc, folder.Name, converted})
	}
	sort.SliceStable(branches, func(i, j int) bool { return branchLess(branches[i].Config.DisplayName, branches[j].Config.DisplayName) })

	if err := os.RemoveAll(outDir); err != nil {
		fatal(err.Error())
	}
	if err := os.MkdirAll(filepath.Join(outDir, "opds"), 0755); err != nil {
		fatal(err.Error())
	}
	if err := writeWeb(outDir, baseURL, branches); err != nil {
		fatal(err.Error())
	}
	if err := writeCatalogJSON(outDir, branches); err != nil {
		fatal(err.Error())
	}
	if err := writeOPDS(outDir, baseURL, branches); err != nil {
		fatal(err.Error())
	}
	fmt.Printf("Generated %d branches at %s (%s)\n", len(branches), outDir, time.Now().Format(time.RFC3339))
}

func getenv(k, d string) string {
	if v := strings.TrimSpace(os.Getenv(k)); v != "" {
		return v
	}
	return d
}
func fatal(s string) { fmt.Fprintln(os.Stderr, s); os.Exit(1) }
func branchLess(a, b string) bool {
	av := strings.HasPrefix(a, "VN")
	bv := strings.HasPrefix(b, "VN")
	if av != bv {
		return av
	}
	return strings.ToLower(a) < strings.ToLower(b)
}
func esc(s string) string  { return html.EscapeString(s) }
func safe(s string) string { return url.PathEscape(s) }
func mime(s string) string {
	if s != "" {
		return s
	}
	return "application/octet-stream"
}
func children(b Branch, parent string) []FileEntry {
	var out []FileEntry
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
func acquisitionURL(f FileEntry) string {
	return "https://drive.usercontent.google.com/download?id=" + url.QueryEscape(f.ID) + "&export=download&confirm=t"
}

func writeWeb(out, base string, branches []Branch) error {
	var b strings.Builder
	b.WriteString(`<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TÀNG THƯ</title><style>body{font:14px Tahoma,Arial;background:#c0c0c0;margin:24px}.w{max-width:1180px;margin:auto;background:#ddd;border:2px solid #fff;border-right-color:#555;border-bottom-color:#555}.t{background:#000080;color:#fff;padding:5px;font-weight:bold}.b{padding:16px}table{width:100%;border-collapse:collapse;background:#fff}th,td{border:1px solid #888;padding:6px;text-align:left}th{background:#ddd}a{color:#000080}.n{background:#ffffcc;border:1px solid #888;padding:8px;margin:10px 0}</style></head><body><div class="w"><div class="t">TÀNG THƯ</div><div class="b"><h2>Thư viện</h2><div class="n">Branch bắt đầu chính xác bằng <b>VN</b> được ưu tiên. Website chỉ là catalog; tải sách dùng OPDS trên máy đọc sách.</div><table><tr><th>Branch</th><th>Google Drive folder</th><th>Files</th></tr>`)
	for _, br := range branches {
		count := 0
		for _, f := range br.Files {
			if !f.IsFolder {
				count++
			}
		}
		b.WriteString(`<tr><td><a href="opds/branch/` + safe(br.Config.ID) + `/index.xml">` + esc(br.Config.DisplayName) + `</a></td><td>` + esc(br.DriveFolderName) + `</td><td>` + fmt.Sprint(count) + `</td></tr>`)
	}
	b.WriteString(`</table><p><a href="opds/index.xml">OPDS</a></p></div></div></body></html>`)
	if err := os.WriteFile(filepath.Join(out, "index.html"), []byte(b.String()), 0644); err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(out, ".nojekyll"), []byte{}, 0644)
}

func writeCatalogJSON(out string, branches []Branch) error {
	type JFile struct {
		ID       string `json:"id"`
		ParentID string `json:"parent_id"`
		Name     string `json:"name"`
		MIME     string `json:"mime"`
		Size     int64  `json:"size"`
		Modified string `json:"modified"`
		Checksum string `json:"checksum,omitempty"`
		Folder   bool   `json:"folder"`
	}
	type JBranch struct {
		ID    string  `json:"id"`
		Name  string  `json:"name"`
		Files []JFile `json:"files"`
	}
	var rows []JBranch
	for _, br := range branches {
		jb := JBranch{ID: br.Config.ID, Name: br.Config.DisplayName}
		for _, f := range br.Files {
			jb.Files = append(jb.Files, JFile{f.ID, f.ParentID, f.Name, f.MIME, f.Size, f.Modified, f.Checksum, f.IsFolder})
		}
		rows = append(rows, jb)
	}
	data, err := json.MarshalIndent(rows, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(out, "catalog.json"), data, 0644)
}

func writeOPDS(out, base string, branches []Branch) error {
	var root strings.Builder
	root.WriteString(xmlHead("TÀNG THƯ"))
	for _, br := range branches {
		root.WriteString(`<entry><title>` + esc(br.Config.DisplayName) + `</title><link rel="subsection" href="` + base + `/opds/branch/` + safe(br.Config.ID) + `/index.xml" type="application/atom+xml;profile=opds-catalog"/></entry>`)
	}
	root.WriteString(`</feed>`)
	if err := writeFile(filepath.Join(out, "opds", "index.xml"), root.String()); err != nil {
		return err
	}

	for _, br := range branches {
		dir := filepath.Join(out, "opds", "branch", br.Config.ID)
		if err := os.MkdirAll(dir, 0755); err != nil {
			return err
		}
		if err := writeBranchOPDS(dir, base, br); err != nil {
			return err
		}
	}
	return nil
}
func xmlHead(title string) string {
	return `<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom" xmlns:opds="http://opds-spec.org/2010/catalog"><title>` + esc(title) + `</title>`
}
func writeBranchOPDS(dir, base string, br Branch) error {
	return writeFolder(dir, base, br, br.Config.RootFolderID, true)
}
func writeFolder(dir, base string, br Branch, folderID string, root bool) error {
	rows := children(br, folderID)
	relName := "index.xml"
	if !root {
		relName = safe(folderID) + ".xml"
	}
	var x strings.Builder
	title := br.Config.DisplayName
	if !root {
		for _, f := range br.Files {
			if f.ID == folderID {
				title += " / " + f.Name
				break
			}
		}
	}
	x.WriteString(xmlHead(title))
	if root {
		x.WriteString(`<link rel="start" href="` + base + `/opds/index.xml" type="application/atom+xml;profile=opds-catalog"/>`)
	}
	for _, f := range rows {
		if f.IsFolder {
			x.WriteString(`<entry><title>` + esc(f.Name) + `</title><link rel="subsection" href="` + base + `/opds/branch/` + safe(br.Config.ID) + `/` + safe(f.ID) + `.xml" type="application/atom+xml;profile=opds-catalog"/></entry>`)
			if err := writeFolder(dir, base, br, f.ID, false); err != nil {
				return err
			}
		} else {
			x.WriteString(`<entry><title>` + esc(f.Name) + `</title><content type="text">` + esc(fmt.Sprintf("%d bytes · %s", f.Size, f.MIME)) + `</content><link rel="acquisition" href="` + esc(acquisitionURL(f)) + `" type="` + esc(mime(f.MIME)) + `"/></entry>`)
		}
	}
	x.WriteString(`</feed>`)
	return writeFile(filepath.Join(dir, relName), x.String())
}
func writeFile(path, s string) error {
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		return err
	}
	return os.WriteFile(path, []byte(s), 0644)
}
