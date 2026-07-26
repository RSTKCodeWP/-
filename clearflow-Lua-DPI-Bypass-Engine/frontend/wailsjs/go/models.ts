export namespace main {
	
	export class ScanResult {
	    success: boolean;
	    engineName: string;
	    profileName: string;
	
	    static createFrom(source: any = {}) {
	        return new ScanResult(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.success = source["success"];
	        this.engineName = source["engineName"];
	        this.profileName = source["profileName"];
	    }
	}
	export class Settings {
	    engineName: string;
	    profileName: string;
	    autostart: boolean;
	
	    static createFrom(source: any = {}) {
	        return new Settings(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.engineName = source["engineName"];
	        this.profileName = source["profileName"];
	        this.autostart = source["autostart"];
	    }
	}

}

