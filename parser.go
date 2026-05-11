package main

import (
	"encoding/xml"
	"io"
	"os"
	"path/filepath"
	"strings"
)

// ─── Public result types (exported to JS via Wails) ────────────────────────

type TreeNode struct {
	Name       string            `json:"name"`
	TypeInfo   string            `json:"typeInfo"`
	Occurs     string            `json:"occurs"`
	Annotation string            `json:"annotation"`
	Color      string            `json:"color"`
	IsAttr     bool              `json:"isAttr"`
	IsChoice   bool              `json:"isChoice"`
	Children   []*TreeNode       `json:"children"`
	Attributes map[string]string `json:"attributes"`
}

type LegendItem struct {
	FileName string `json:"fileName"`
	Color    string `json:"color"`
}

type LoadResult struct {
	Nodes  []*TreeNode  `json:"nodes"`
	Legend []LegendItem `json:"legend"`
	Error  string       `json:"error,omitempty"`
}

// ─── Internal XML node ─────────────────────────────────────────────────────

type xmlNode struct {
	tag      string            // local name, e.g. "element"
	attrs    map[string]string // local-name -> value
	ns       map[string]string // prefix -> URI (inherited)
	targetNS string
	filePath string
	children []*xmlNode
}

func (n *xmlNode) attr(name string) string { return n.attrs[name] }

// ─── Parser state ───────────────────────────────────────────────────────────

var colorPalette = []string{
	"#FCE4EC", "#E8F5E9", "#FFFDE7", "#E1F5FE",
	"#EDE7F6", "#E0F7FA", "#FFF3E0", "#ECEFF1",
}

type parser struct {
	filesMap  map[string]string   // absPath -> color
	typesReg  map[nsKey]*xmlNode  // (nsURI, localName) -> node
	elemsReg  map[nsKey]*xmlNode  // (nsURI, localName) -> node
	fileOfType map[*xmlNode]string // node -> absPath
	colorIdx  int
}

type nsKey struct{ uri, local string }

func parseXSD(path string) LoadResult {
	p := &parser{
		filesMap:   make(map[string]string),
		typesReg:   make(map[nsKey]*xmlNode),
		elemsReg:   make(map[nsKey]*xmlNode),
		fileOfType: make(map[*xmlNode]string),
	}
	p.scanSchema(path)

	root, err := loadXML(path)
	if err != nil {
		return LoadResult{Error: err.Error()}
	}

	var nodes []*TreeNode
	for _, child := range root.children {
		if child.tag == "element" {
			nodes = append(nodes, p.createNode(child, path, make(map[string]bool), ""))
		}
	}

	legend := make([]LegendItem, 0, len(p.filesMap))
	// preserve insertion order via filesMap (order not guaranteed in map, but good enough)
	seen := make(map[string]bool)
	for i := 0; i < p.colorIdx; i++ {
		color := colorPalette[i%len(colorPalette)]
		for fp, c := range p.filesMap {
			if c == color && !seen[fp] {
				legend = append(legend, LegendItem{FileName: filepath.Base(fp), Color: color})
				seen[fp] = true
			}
		}
	}

	return LoadResult{Nodes: nodes, Legend: legend}
}

// ─── Schema scanning ────────────────────────────────────────────────────────

func (p *parser) scanSchema(path string) {
	abs, _ := filepath.Abs(path)
	if _, already := p.filesMap[abs]; already {
		return
	}
	color := colorPalette[p.colorIdx%len(colorPalette)]
	p.filesMap[abs] = color
	p.colorIdx++

	root, err := loadXML(abs)
	if err != nil {
		return
	}

	tns := root.attr("targetNamespace")
	for _, child := range root.children {
		name := child.attr("name")
		if name == "" {
			continue
		}
		key := nsKey{tns, name}
		child.filePath = abs
		child.targetNS = tns
		if child.tag == "element" {
			p.elemsReg[key] = child
			p.fileOfType[child] = abs
		} else if child.tag == "complexType" || child.tag == "simpleType" {
			p.typesReg[key] = child
			p.fileOfType[child] = abs
		}
	}

	dir := filepath.Dir(abs)
	for _, child := range root.children {
		if child.tag == "import" || child.tag == "include" {
			loc := child.attr("schemaLocation")
			if loc == "" {
				continue
			}
			full := filepath.Join(dir, loc)
			full, _ = filepath.Abs(full)
			if _, err := os.Stat(full); err == nil {
				p.scanSchema(full)
			}
		}
	}
}

// ─── Tree building ──────────────────────────────────────────────────────────

func (p *parser) createNode(node *xmlNode, file string, visited map[string]bool, prefix string) *TreeNode {
	// resolve ref
	if node.attr("name") == "" && node.attr("ref") != "" {
		uri, local := resolveQName(node.attr("ref"), node)
		if res, ok := p.elemsReg[nsKey{uri, local}]; ok {
			file = p.fileOfType[res]
			node = res
		}
	}
	name := node.attr("name")
	if name == "" {
		name = "[" + node.tag + "]"
	}

	// collapse *List elements that wrap a single child
	displayName := prefix + name
	typeStr := node.attr("type")
	occurs := occursStr(node, "1", "1")
	targetNode := node
	targetFile := file
	isChoice := prefix == "● "

	if strings.HasSuffix(name, "List") {
		if inner, innerFile := p.collapseList(node, file); inner != nil {
			childName := inner.attr("name")
			if childName == "" {
				childName = "[anonymous]"
			}
			displayName = prefix + name + " (" + childName + ")"
			typeStr = inner.attr("type")
			occurs = occursStr(inner, "1", "unbounded")
			targetNode = inner
			targetFile = innerFile
		}
	}

	color := p.colorFor(targetNode, typeStr, targetFile)

	tn := &TreeNode{
		Name:       displayName,
		TypeInfo:   typeStr,
		Occurs:     occurs,
		Annotation: extractAnnotation(node),
		Color:      color,
		IsChoice:   isChoice,
		Attributes: p.allAttributes(targetNode, typeStr),
	}

	p.findChildren(targetNode, targetFile, visited, typeStr, tn)
	return tn
}

func (p *parser) collapseList(node *xmlNode, file string) (*xmlNode, string) {
	cts := childrenByTag(node, "complexType")
	if len(cts) != 1 {
		return nil, ""
	}
	seqs := childrenByTag(cts[0], "sequence")
	if len(seqs) != 1 {
		return nil, ""
	}
	elems := childrenByTag(seqs[0], "element")
	if len(elems) != 1 {
		return nil, ""
	}
	inner := elems[0]
	innerFile := file
	if inner.attr("name") == "" && inner.attr("ref") != "" {
		uri, local := resolveQName(inner.attr("ref"), inner)
		if res, ok := p.elemsReg[nsKey{uri, local}]; ok {
			inner = res
			innerFile = p.fileOfType[res]
		}
	}
	return inner, innerFile
}

func (p *parser) findChildren(node *xmlNode, file string, visited map[string]bool, typeStr string, parent *TreeNode) {
	for _, ct := range childrenByTag(node, "complexType") {
		p.processStructure(ct, file, visited, parent)
	}
	if typeStr != "" {
		uri, local := resolveQName(typeStr, node)
		key := nsKey{uri, local}
		if res, ok := p.typesReg[key]; ok && !visited[typeStr] {
			visited[typeStr] = true
			resFile := p.fileOfType[res]
			p.processStructure(res, resFile, visited, parent)
			delete(visited, typeStr)
		}
	}
}

func (p *parser) processStructure(struct_ *xmlNode, file string, visited map[string]bool, parent *TreeNode) {
	// process extensions first (inherited fields)
	for _, ext := range findExtensions(struct_) {
		base := ext.attr("base")
		if base == "" {
			continue
		}
		uri, local := resolveQName(base, ext)
		if res, ok := p.typesReg[nsKey{uri, local}]; ok {
			p.processStructure(res, p.fileOfType[res], visited, parent)
		}
		// attributes from extension
		for _, attr := range childrenByTag(ext, "attribute") {
			tn := p.createAttributeNode(attr, file)
			if tn != nil {
				parent.Children = append(parent.Children, tn)
			}
		}
		// child elements from extension
		for _, child := range getChildElements(ext) {
			pref := choicePrefix(child)
			parent.Children = append(parent.Children, p.createNode(child, file, visited, pref))
		}
	}

	// direct attributes
	for _, attr := range directAttributes(struct_) {
		tn := p.createAttributeNode(attr, file)
		if tn != nil {
			parent.Children = append(parent.Children, tn)
		}
	}

	// direct child elements
	for _, child := range getChildElements(struct_) {
		pref := choicePrefix(child)
		parent.Children = append(parent.Children, p.createNode(child, file, visited, pref))
	}
}

func (p *parser) createAttributeNode(attr *xmlNode, file string) *TreeNode {
	name := attr.attr("name")
	if name == "" && attr.attr("ref") != "" {
		_, local := resolveQName(attr.attr("ref"), attr)
		name = local
	}
	if name == "" {
		return nil
	}

	typeStr := attr.attr("type")
	use := attr.attr("use")
	if use == "" {
		use = "optional"
	}
	color := p.colorFor(attr, typeStr, file)

	return &TreeNode{
		Name:       "@" + name,
		TypeInfo:   typeStr,
		Occurs:     "[" + use + "]",
		Annotation: extractAnnotation(attr),
		Color:      color,
		IsAttr:     true,
		Attributes: p.allAttributes(attr, typeStr),
	}
}

func (p *parser) colorFor(node *xmlNode, typeStr string, file string) string {
	abs, _ := filepath.Abs(file)
	color := p.filesMap[abs]
	if color == "" {
		color = "#FFFFFF"
	}
	if typeStr != "" {
		uri, local := resolveQName(typeStr, node)
		// xs: builtins → white
		if uri == "http://www.w3.org/2001/XMLSchema" {
			return "#FFFFFF"
		}
		if res, ok := p.typesReg[nsKey{uri, local}]; ok {
			resFile := p.fileOfType[res]
			absRes, _ := filepath.Abs(resFile)
			if c, ok := p.filesMap[absRes]; ok {
				return c
			}
		}
	}
	return color
}

func (p *parser) allAttributes(node *xmlNode, typeStr string) map[string]string {
	data := make(map[string]string)
	for k, v := range node.attrs {
		if k == "name" || k == "ref" {
			continue
		}
		data[k] = v
	}
	if typeStr != "" {
		uri, local := resolveQName(typeStr, node)
		if res, ok := p.typesReg[nsKey{uri, local}]; ok {
			collectFacets(res, data)
		}
	}
	return data
}

func collectFacets(node *xmlNode, out map[string]string) {
	facetTags := map[string]bool{
		"pattern": true, "minLength": true, "maxLength": true,
		"minInclusive": true, "maxInclusive": true,
		"totalDigits": true, "fractionDigits": true,
	}
	var walk func(*xmlNode)
	walk = func(n *xmlNode) {
		for _, c := range n.children {
			if facetTags[c.tag] {
				out[c.tag] = c.attr("value")
			} else if c.tag == "enumeration" {
				existing := out["enumeration"]
				v := c.attr("value")
				if existing == "" {
					out["enumeration"] = v
				} else {
					out["enumeration"] = existing + ", " + v
				}
			} else {
				walk(c)
			}
		}
	}
	walk(node)
}

// ─── XML helpers ────────────────────────────────────────────────────────────

func childrenByTag(n *xmlNode, tag string) []*xmlNode {
	var res []*xmlNode
	for _, c := range n.children {
		if c.tag == tag {
			res = append(res, c)
		}
	}
	return res
}

func getChildElements(n *xmlNode) []*xmlNode {
	var res []*xmlNode
	for _, c := range n.children {
		switch c.tag {
		case "element":
			res = append(res, c)
		case "sequence", "choice", "all":
			res = append(res, getChildElements(c)...)
		}
	}
	return res
}

func findExtensions(n *xmlNode) []*xmlNode {
	var res []*xmlNode
	for _, c := range n.children {
		if c.tag == "complexContent" || c.tag == "simpleContent" {
			for _, gc := range c.children {
				if gc.tag == "extension" {
					res = append(res, gc)
				}
			}
		}
	}
	return res
}

func directAttributes(n *xmlNode) []*xmlNode {
	var res []*xmlNode
	for _, c := range n.children {
		if c.tag == "attribute" {
			res = append(res, c)
		}
	}
	return res
}

func choicePrefix(n *xmlNode) string {
	if isChoiceVariant(n) {
		return "● "
	}
	return ""
}

func isChoiceVariant(n *xmlNode) bool {
	// parent set during load
	return n.attrs["_inChoice"] == "1"
}

func occursStr(n *xmlNode, defMin, defMax string) string {
	min := n.attr("minOccurs")
	if min == "" {
		min = defMin
	}
	max := n.attr("maxOccurs")
	if max == "" {
		max = defMax
	}
	return "[" + min + ".." + max + "]"
}

func extractAnnotation(n *xmlNode) string {
	for _, c := range n.children {
		if c.tag == "annotation" {
			for _, d := range c.children {
				if d.tag == "documentation" {
					var parts []string
					for _, t := range d.children {
						if t.tag == "_text" {
							parts = append(parts, t.attrs["_text"])
						}
					}
					return strings.Join(strings.Fields(strings.Join(parts, " ")), " ")
				}
			}
		}
	}
	return ""
}

// resolveQName converts "prefix:local" or "local" to (namespaceURI, localName)
func resolveQName(qname string, n *xmlNode) (string, string) {
	if qname == "" {
		return "", ""
	}
	var prefix, local string
	if idx := strings.Index(qname, ":"); idx >= 0 {
		prefix = qname[:idx]
		local = qname[idx+1:]
	} else {
		local = qname
	}
	uri := n.ns[prefix]
	if uri == "" && prefix == "" {
		uri = n.targetNS
	}
	return uri, local
}

// ─── Raw XML loader ─────────────────────────────────────────────────────────

func loadXML(path string) (*xmlNode, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	dec := xml.NewDecoder(f)
	root, _, err := readNode(dec, make(map[string]string), "")
	return root, err
}

func readNode(dec *xml.Decoder, parentNS map[string]string, parentTargetNS string) (*xmlNode, bool, error) {
	for {
		tok, err := dec.Token()
		if err != nil {
			if err == io.EOF {
				return nil, true, nil
			}
			return nil, false, err
		}
		switch se := tok.(type) {
		case xml.StartElement:
			node := &xmlNode{
				tag:      se.Name.Local,
				attrs:    make(map[string]string),
				ns:       make(map[string]string),
				targetNS: parentTargetNS,
			}
			// inherit parent namespaces
			for k, v := range parentNS {
				node.ns[k] = v
			}
			// parse attributes + xmlns
			for _, a := range se.Attr {
				if a.Name.Space == "xmlns" {
					node.ns[a.Name.Local] = a.Value
				} else if a.Name.Space == "" && a.Name.Local == "xmlns" {
					node.ns[""] = a.Value
				} else {
					node.attrs[a.Name.Local] = a.Value
				}
			}
			if tns, ok := node.attrs["targetNamespace"]; ok {
				node.targetNS = tns
			}
			// mark children of <choice> for prefix rendering
			if node.tag == "choice" {
				// will mark direct element children below
			}
			// read children
			for {
				child, done, err := readNode(dec, node.ns, node.targetNS)
				if err != nil {
					return nil, false, err
				}
				if done {
					break
				}
				child.targetNS = node.targetNS
				// mark elements inside choice
				if node.tag == "choice" && child.tag == "element" {
					child.attrs["_inChoice"] = "1"
				}
				node.children = append(node.children, child)
			}
			return node, false, nil

		case xml.EndElement:
			return nil, true, nil

		case xml.CharData:
			// will be captured as _text if parent is documentation
			// handled via a special check — we set it on the parent after the fact
			// simpler: return a text pseudo-node
			text := strings.TrimSpace(string(se))
			if text != "" {
				return &xmlNode{tag: "_text", attrs: map[string]string{"_text": text}, ns: parentNS, targetNS: parentTargetNS}, false, nil
			}
		}
	}
}
