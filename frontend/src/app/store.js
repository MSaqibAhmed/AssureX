import { configureStore, createSlice } from '@reduxjs/toolkit';
import { api, setCsrf } from '../api/client';
const anonymous = { authenticated: false, user: null, role: null, ready: false };
const slice = createSlice({
  name: 'app',
  initialState: { session: anonymous, toast: null },
  reducers: {
    signedIn(state, { payload: user }) {
      state.session = {
        ready: true,
        authenticated: true,
        role: user.role,
        user: {
          ...user,
          initials: user.name
            .split(' ')
            .map((n) => n[0])
            .slice(0, 2)
            .join(''),
        },
      };
    },
    signedOut(state) {
      state.session = { ...anonymous, ready: true };
    },
    toast(state, { payload }) {
      state.toast = payload;
    },
  },
});
export const actions = slice.actions;
export default slice.reducer;
export const store = configureStore({ reducer: { app: slice.reducer } });
export function acceptSession(data) {
  setCsrf(data.csrf_token);
  store.dispatch(actions.signedIn(data.user));
}
export async function logout() {
  await api.post('/auth/logout');
  setCsrf(null);
  store.dispatch(actions.signedOut());
}
