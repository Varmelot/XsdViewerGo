export namespace main {
	
	export class LegendItem {
	    fileName: string;
	    color: string;
	
	    static createFrom(source: any = {}) {
	        return new LegendItem(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.fileName = source["fileName"];
	        this.color = source["color"];
	    }
	}
	export class TreeNode {
	    name: string;
	    typeInfo: string;
	    occurs: string;
	    annotation: string;
	    color: string;
	    isAttr: boolean;
	    isChoice: boolean;
	    children: TreeNode[];
	    attributes: Record<string, string>;
	
	    static createFrom(source: any = {}) {
	        return new TreeNode(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.name = source["name"];
	        this.typeInfo = source["typeInfo"];
	        this.occurs = source["occurs"];
	        this.annotation = source["annotation"];
	        this.color = source["color"];
	        this.isAttr = source["isAttr"];
	        this.isChoice = source["isChoice"];
	        this.children = this.convertValues(source["children"], TreeNode);
	        this.attributes = source["attributes"];
	    }
	
		convertValues(a: any, classs: any, asMap: boolean = false): any {
		    if (!a) {
		        return a;
		    }
		    if (a.slice && a.map) {
		        return (a as any[]).map(elem => this.convertValues(elem, classs));
		    } else if ("object" === typeof a) {
		        if (asMap) {
		            for (const key of Object.keys(a)) {
		                a[key] = new classs(a[key]);
		            }
		            return a;
		        }
		        return new classs(a);
		    }
		    return a;
		}
	}
	export class LoadResult {
	    nodes: TreeNode[];
	    legend: LegendItem[];
	    error?: string;
	
	    static createFrom(source: any = {}) {
	        return new LoadResult(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.nodes = this.convertValues(source["nodes"], TreeNode);
	        this.legend = this.convertValues(source["legend"], LegendItem);
	        this.error = source["error"];
	    }
	
		convertValues(a: any, classs: any, asMap: boolean = false): any {
		    if (!a) {
		        return a;
		    }
		    if (a.slice && a.map) {
		        return (a as any[]).map(elem => this.convertValues(elem, classs));
		    } else if ("object" === typeof a) {
		        if (asMap) {
		            for (const key of Object.keys(a)) {
		                a[key] = new classs(a[key]);
		            }
		            return a;
		        }
		        return new classs(a);
		    }
		    return a;
		}
	}

}

