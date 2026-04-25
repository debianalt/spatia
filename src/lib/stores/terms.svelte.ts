const TERMS_KEY = 'spatia_terms_v1';

class TermsStore {
	accepted: boolean = $state(false);

	constructor() {
		if (typeof window !== 'undefined') {
			this.accepted = localStorage.getItem(TERMS_KEY) === 'true';
		}
	}

	accept() {
		this.accepted = true;
		if (typeof window !== 'undefined') {
			localStorage.setItem(TERMS_KEY, 'true');
		}
	}
}

export const terms = new TermsStore();
