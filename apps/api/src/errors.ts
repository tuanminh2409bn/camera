export class ApiFailure extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}
export const unauthorized = () =>
  new ApiFailure(401, "UNAUTHORIZED", "Vui lòng đăng nhập lại.");
export const forbidden = () =>
  new ApiFailure(
    403,
    "FORBIDDEN",
    "Bạn không có quyền thực hiện thao tác này.",
  );
export const offline = () =>
  new ApiFailure(
    503,
    "UPSTREAM_OFFLINE",
    "Nguồn camera hoặc dịch vụ đang ngoại tuyến. Vui lòng thử lại.",
  );
