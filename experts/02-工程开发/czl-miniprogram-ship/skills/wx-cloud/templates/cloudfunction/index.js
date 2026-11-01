// 云函数骨架：复制整个目录，改名后即可部署
// 纪律：身份从上下文取、入参必校验、统一返回结构、错误不外泄
const cloud = require('wx-server-sdk');
cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV });

const db = cloud.database();

exports.main = async (event, context) => {
  const { OPENID } = cloud.getWXContext();
  if (!OPENID) return { code: 401, msg: '未登录' };

  const action = event.action || 'default';
  try {
    switch (action) {
      case 'default':
        return await handleDefault(event, OPENID);
      default:
        return { code: 400, msg: '未知操作' };
    }
  } catch (e) {
    console.error('[handler error]', action, e);   // 日志只留服务端
    return { code: 500, msg: '服务开小差了，请稍后再试' };
  }
};

async function handleDefault(event, openid) {
  // ① 入参校验
  if (!event.id || typeof event.id !== 'string') {
    return { code: 400, msg: '参数不合法' };
  }

  // ② 业务（示例：只读自己的一条记录）
  const res = await db.collection('your_collection')
    .where({ _id: event.id, _openid: openid })
    .get();
  if (!res.data.length) return { code: 403, msg: '无权访问' };

  // ③ 统一返回
  return { code: 0, data: res.data[0] };
}
